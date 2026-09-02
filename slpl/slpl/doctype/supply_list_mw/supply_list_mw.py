# Copyright (c) 2026, GreyCube Technologies and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt
from frappe.utils.nestedset import get_descendants_of
from frappe.contacts.doctype.address.address import get_address_display


FINISH_GOODS_ITEM_GROUP = "FINISH GOODS"
PACKING_INITIATED_THRESHOLD = 15  # percent - above this, status moves from "Initiated" to "Partially Delivered"


class SupplyListMW(Document):
	def validate(self):
		self.get_bom_wise_items()
		self.calculate_packing_status()

	def get_all_finish_goods_groups(self):
		return [FINISH_GOODS_ITEM_GROUP] + get_descendants_of(
			"Item Group", FINISH_GOODS_ITEM_GROUP, ignore_permissions=True
		)

	def get_all_boughtout_groups(self):
		mech_settings = frappe.get_doc("Mechwell Setting MW")

		boughtout_groups = [mech_settings.default_item_group_for_bought_out]
		boughtout_childs = frappe.get_all(
			"Item Group", {"parent_item_group": mech_settings.default_item_group_for_bought_out}, ["name"]
		)
		for group in boughtout_childs:
			boughtout_groups.append(group.name)
		return boughtout_groups

	def get_all_sub_assembly_groups(self):
		mech_settings = frappe.get_doc("Mechwell Setting MW")

		sub_assembly_groups = [mech_settings.default_item_group_for_sub_assembly]
		sub_assembly_childs = frappe.get_all(
			"Item Group", {"parent_item_group": mech_settings.default_item_group_for_sub_assembly}, ["name"]
		)
		for group in sub_assembly_childs:
			sub_assembly_groups.append(group.name)
		return sub_assembly_groups

	def classify_item_group(self, item_group, finish_goods_groups, sub_assembly_groups, boughtout_groups):
		if item_group in finish_goods_groups:
			return "Finished Good"
		if item_group in sub_assembly_groups:
			return "Sub-Assembly"
		if item_group in boughtout_groups:
			return "Bought Out"
		return item_group

	def get_serial_no_of_finished_good_using_bom(self, bom, item):
		serial_no = None
		work_order = frappe.db.get_value(
			"Work Order", {
				"production_item": item,
				"bom_no": bom,
			},
			"name"
		)
		if work_order:
			serial_no = frappe.db.get_all(
				"Serial No", {
					"work_order": work_order,
					"item_code": item,
				},
				["name"],
				order_by="creation",
			)
		return serial_no

	# -----------------------------------------------------------------
	# Tag No / Serial No assignment (Refresh BOM Details button)
	# -----------------------------------------------------------------
	@frappe.whitelist()
	def get_tag_no_for_bom_details(self):
		found = 0
		not_found = 0
		used_tag_nos = {row.tag_no for row in self.bom_details if row.tag_no}

		for row in self.bom_details:
			if row.tag_no or not row.bom:
				continue

			work_order = frappe.db.get_value(
				"Work Order", {
					"production_item": row.item,
					"bom_no": row.bom,
				},
				"name",
				order_by="creation desc"
			)

			tag_no = None
			if work_order:
				filters = {
					"work_order": work_order,
					"item_code": row.item,
				}
				if used_tag_nos:
					filters["name"] = ["not in", list(used_tag_nos)]

				tag_no = frappe.db.get_value(
					"Serial No", filters,
					"name",
					order_by="creation"
				)

			if tag_no:
				row.tag_no = tag_no
				used_tag_nos.add(tag_no)
				found += 1

				for item_row in self.items:
					if item_row.bom_details_item_row == row.name:
						item_row.tag_no__sr_no = tag_no
			else:
				not_found += 1

		if found:
			self.save(ignore_permissions=True)

		return {"found": found, "not_found": not_found}

	# -----------------------------------------------------------------
	# Items table: 0-level BOM items + bought-out items from sub-BOMs
	# -----------------------------------------------------------------
	def get_bom_wise_items(self):
		bom_wise_items = []
		if self.bom_details:
			for bom_detail in self.bom_details:
				if not bom_detail.bom:
					continue

				bom_doc = frappe.get_doc("BOM", bom_detail.bom)

				for bom_item in bom_doc.items:
					item_data = frappe.db.get_value(
						"Item",
						bom_item.item_code,
						["brand", "description"],
						as_dict=True
					) or {}

					# Main BOM / Zero-level item
					bom_wise_items.append({
						"item_code": bom_item.item_code,
						"quantity": bom_item.qty,
						"brand": item_data.get("brand"),
						"sales_order_item": bom_detail.item,
						"tag_no__sr_no": bom_detail.tag_no or None,
						"bom": bom_detail.bom,
						"description": item_data.get("description"),
						"bom_details_item_row": bom_detail.name,
					})

					# If zero-level item has a BOM, find bought-out items from its child BOM hierarchy
					if bom_item.bom_no:
						boughtout_items = self.get_zero_assemblies_and_boughout_items(
							bom_item.bom_no, bom_detail.item, bom_detail.tag_no or None, bom_detail.bom, bom_detail.name
						)

						if boughtout_items:
							bom_wise_items.extend(boughtout_items)

					bom_detail.finished_good_status = "Added In Supply List"
			self.items = []
			for item in bom_wise_items:
				self.append("items", item)

	def calculate_packing_status(self):
		for bom_detail in self.bom_details:
			rows = [row for row in self.items if row.bom_details_item_row == bom_detail.name]
			total_qty = sum(flt(row.quantity) for row in rows)
			delivered_qty = sum(flt(row.delivered_qty) for row in rows)

			percentage = (delivered_qty / total_qty * 100) if total_qty else 0
			bom_detail.packing_percentage = percentage

			if percentage >= 100:
				bom_detail.packing_status = "Fully Delivered"
			elif percentage > PACKING_INITIATED_THRESHOLD:
				bom_detail.packing_status = "Partially Delivered"
			elif percentage > 0:
				bom_detail.packing_status = "Initiated"
			else:
				bom_detail.packing_status = "Not Started"

	def get_zero_assemblies_and_boughout_items(self, bom, sales_order_item, tag_no, main_bom_no, bom_details_item_name):
		boughtout_groups = self.get_all_boughtout_groups()
		return self.process_bom(
			bom,
			boughtout_groups,
			sales_order_item,
			tag_no,
			main_bom_no,
			bom_details_item_name
		)

	def process_bom(self, bom_no, boughtout_groups, sales_order_item=None, tag_no=None, main_bom_no=None, bom_details_item_name=None):
		items = []
		bom_doc = frappe.get_doc("BOM", bom_no)
		for item in bom_doc.items:
			item_data = frappe.db.get_value(
				"Item",
				item.item_code,
				["item_group", "brand", "description"],
				as_dict=True
			) or {}

			# Only bought-out items from child BOMs
			item_group = item_data.get("item_group")
			if item_group in boughtout_groups:
				items.append({
					"item_code": item.item_code,
					"quantity": item.qty,
					"uom": item.uom,
					"brand": item_data.get("brand"),
					"description": item_data.get("description"),
					"sales_order_item": sales_order_item,
					"tag_no__sr_no": tag_no,
					"bom": main_bom_no,
					"bom_details_item_row": bom_details_item_name,
				})

			# If bought-out item itself has a BOM, continue traversing its BOM
			if item.bom_no:
				child_items = self.process_bom(
					item.bom_no,
					boughtout_groups,
					sales_order_item,
					tag_no,
					main_bom_no,
					bom_details_item_name
				)

				if child_items:
					items.extend(child_items)

		return items

	@frappe.whitelist()
	def refresh_items(self):
		# Rows already (partially) delivered are frozen and must not be touched,
		# even if the source BOM changed since they were added.
		locked_rows = {row.bom_details_item_row for row in self.items if row.delivered_qty}
		new_items = [row.as_dict() for row in self.items if row.bom_details_item_row in locked_rows]

		for bom_detail in self.bom_details:
			if not bom_detail.bom or bom_detail.name in locked_rows:
				continue

			bom_doc = frappe.get_doc("BOM", bom_detail.bom)

			for bom_item in bom_doc.items:
				item_data = frappe.db.get_value(
					"Item",
					bom_item.item_code,
					["brand", "description"],
					as_dict=True
				) or {}

				new_items.append({
					"item_code": bom_item.item_code,
					"quantity": bom_item.qty,
					"brand": item_data.get("brand"),
					"sales_order_item": bom_detail.item,
					"tag_no__sr_no": bom_detail.tag_no or None,
					"bom": bom_detail.bom,
					"description": item_data.get("description"),
					"bom_details_item_row": bom_detail.name,
				})

				if bom_item.bom_no:
					boughtout_items = self.get_zero_assemblies_and_boughout_items(
						bom_item.bom_no, bom_detail.item, bom_detail.tag_no or None, bom_detail.bom, bom_detail.name
					)
					if boughtout_items:
						new_items.extend(boughtout_items)

				bom_detail.finished_good_status = "Added In Supply List"

		self.items = []
		for item in new_items:
			self.append("items", item)

		self.save(ignore_permissions=True)

	# -----------------------------------------------------------------
	# BOM Tree view (Show BOM Tree button)
	# -----------------------------------------------------------------
	@frappe.whitelist()
	def get_bom_tree(self, bom):
		finish_goods_groups = self.get_all_finish_goods_groups()
		sub_assembly_groups = self.get_all_sub_assembly_groups()
		boughtout_groups = self.get_all_boughtout_groups()

		bom_doc = frappe.get_doc("BOM", bom)
		root_item_name = frappe.db.get_value("Item", bom_doc.item, "item_name")

		children = []
		for bom_item in bom_doc.items:
			item_data = frappe.db.get_value(
				"Item", bom_item.item_code, ["item_group", "item_name"], as_dict=True
			) or {}

			node_children = []
			if bom_item.bom_no:
				for boughtout_item in self.get_zero_assemblies_and_boughout_items(
					bom_item.bom_no, None, None, None, None
				):
					node_children.append({
						"item_code": boughtout_item["item_code"],
						"item_name": frappe.db.get_value("Item", boughtout_item["item_code"], "item_name"),
						"qty": boughtout_item["quantity"],
						"uom": boughtout_item.get("uom"),
						"category": "Bought Out",
						"children": [],
					})

			children.append({
				"item_code": bom_item.item_code,
				"item_name": item_data.get("item_name"),
				"qty": bom_item.qty,
				"uom": bom_item.uom,
				"category": self.classify_item_group(
					item_data.get("item_group"), finish_goods_groups, sub_assembly_groups, boughtout_groups
				),
				"children": node_children,
			})

		return {
			"item_code": bom_doc.item,
			"item_name": root_item_name,
			"qty": bom_doc.quantity,
			"uom": bom_doc.uom,
			"category": "Finished Good",
			"children": children,
		}

# -----------------------------------------------------------------
# Project -> Sales Order -> BOM Details (on selecting Project)
# -----------------------------------------------------------------
@frappe.whitelist()
def get_finished_goods_of_sales_order_with_bom_items(doc):
	# Reconstructed from the full in-memory doc (not looked up by name) because
	# this runs on a brand-new, unsaved document - it has no row in the DB yet.
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	self = frappe.get_doc(doc)
	if self.project:
		project_doc = frappe.get_doc("Project", self.project)
		if project_doc.sales_order:
			self.sales_order = project_doc.sales_order
			self.client = frappe.db.get_value("Sales Order", self.sales_order, "customer")
		else:
			frappe.throw(f"Sales Order is not assigned in Project <b>{self.project}</b>")

	sales_order = frappe.get_doc("Sales Order", project_doc.sales_order)
	if sales_order:
		finish_goods_groups = self.get_all_finish_goods_groups()
		for item in sales_order.items:
			item_group = frappe.db.get_value("Item", item.item_code, "item_group")
			if item_group not in finish_goods_groups:
				continue

			default_bom = frappe.db.get_value(
				"BOM", {
					"item": item.item_code,
					"is_default": 1,
					"docstatus": 1,
					"is_active": 1
				},
				"name"
			)
			if default_bom:
				bom_status = "BOM Exist"
				serial_no = self.get_serial_no_of_finished_good_using_bom(default_bom, item.item_code)
			else:
				bom_status = "BOM Does Not Exist"
				serial_no = None

			if serial_no:
				serial_no = [s['name'] for s in serial_no]
			else:
				if item.custom_serial_no:
					serial_no = [sn.strip() for sn in item.custom_serial_no.split(",") if sn.strip()]

			if item.qty > 1:
				for i in range(int(item.qty)):
					self.append("bom_details", {
						"qty": 1,
						"item": item.item_code,
						"bom": default_bom,
						"bom_status": bom_status,
						"finished_good_status": "Not Added In Supply List",
						"tag_no": serial_no[i] if serial_no and len(serial_no) > i else None
					})
			elif item.qty == 1:
				self.append("bom_details", {
					"qty": item.qty,
					"item": item.item_code,
					"bom": default_bom,
					"bom_status": bom_status,
					"finished_good_status": "Not Added In Supply List",
					"tag_no": serial_no[0] if serial_no else None
				})
		self.save(ignore_permissions=True)

	return self


# ---------------------------------------------------------------------------------
# Standalone endpoints (Additional Items / Fetch BOM / Create Packing List buttons)
# ---------------------------------------------------------------------------------
def get_stock_validation_warehouse():
	return frappe.get_doc("Mechwell Setting MW").default_warehouse_to_validate_quantity


@frappe.whitelist()
def get_warehouse_stock_qty(item_codes):
	if isinstance(item_codes, str):
		item_codes = frappe.parse_json(item_codes)

	warehouse = get_stock_validation_warehouse()
	if not warehouse or not item_codes:
		return {}

	bins = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": warehouse},
		fields=["item_code", "actual_qty"],
	)
	return {b.item_code: b.actual_qty for b in bins}


@frappe.whitelist()
def validate_stock_availability(items):
	if isinstance(items, str):
		items = frappe.parse_json(items)

	warehouse = get_stock_validation_warehouse()
	if not warehouse:
		frappe.throw(
			_("Please configure <b>Default Warehouse to Validate Quantity</b> in Mechwell Setting MW")
		)

	# Aggregate by item_code first, in case the same item appears in more
	# than one row, so the check reflects the total quantity actually needed.
	required_qty_by_item = {}
	for item in items:
		item_code = item.get("item_code")
		qty = flt(item.get("qty"))
		if not item_code or qty <= 0:
			continue
		required_qty_by_item[item_code] = required_qty_by_item.get(item_code, 0) + qty

	shortages = []
	for item_code, required_qty in required_qty_by_item.items():
		available_qty = flt(
			frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
		)
		if available_qty < required_qty:
			shortages.append(
				_("{0}: required {1}, available {2}").format(item_code, required_qty, available_qty)
			)

	if shortages:
		frappe.throw(
			_("Insufficient stock in warehouse {0} for:<br>{1}").format(
				frappe.bold(warehouse), "<br>".join(shortages)
			)
		)


@frappe.whitelist()
def make_packing_list(source_name, target_doc=None):
	selected_items = (frappe.flags.args or {}).get("selected_items")
	if isinstance(selected_items, str):
		selected_items = json.loads(selected_items)

	def set_missing_values(source, target):
		customer_address = frappe.db.get_all(
            "Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": source.client},
            pluck="parent"
        )
		if customer_address:
			target.destination = get_address_display(customer_address[0]).replace("<br>", "\n")

		target.ack_no = source.project
		target.customer = source.client
		target.sales_order = source.sales_order
		target.supply_list_reference = source.name
		target.product_name = frappe.flags.args.get("product_name")
		target.quantity = frappe.flags.args.get("quantity")

		for row in selected_items or []:
			target.append("packing_items", {
				"item_code": row.get("item_code"),
				"qty": row.get("qty_to_pack"),
				"supply_row_name": row.get("supply_row_name"),
				"is_additional_item": row.get("is_additional_item")
			})

	return get_mapped_doc(
		"Supply List MW",
		source_name,
		{
			"Supply List MW": {
				"doctype": "Packing List MW",
			}
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def get_additional_items_of_bom(bom):
	bom_doc = frappe.get_doc("BOM", bom)
	items = []
	for bom_item in bom_doc.items:
		item_data = frappe.db.get_value(
			"Item",
			bom_item.item_code,
			["brand", "description"],
			as_dict=True
		) or {}
		items.append({
			"item_code": bom_item.item_code,
			"quantity": bom_item.qty,
			"brand": item_data.get("brand"),
			"description": item_data.get("description"),
		})
	return items


@frappe.whitelist()
def get_default_bom_of_finished_items_of_sales_order(item):
	default_bom = frappe.db.get_value(
		"BOM", {
			"item": item,
			"is_default": 1,
			"docstatus": 1,
			"is_active": 1
		},
		"name",
		order_by="creation desc"
	)
	return default_bom


def recalculate_packing_status(supply_list_name):
	# Called from Packing List MW on submit/cancel so bom_details reflects the
	# latest packing status immediately, without a full Supply List MW save
	# (which would run get_bom_wise_items() and rebuild the items table).
	doc = frappe.get_doc("Supply List MW", supply_list_name)
	doc.calculate_packing_status()

	for bom_detail in doc.bom_details:
		frappe.db.set_value(
			"Supply List Finished Good BOM Detail MW",
			bom_detail.name,
			{
				"packing_percentage": bom_detail.packing_percentage,
				"packing_status": bom_detail.packing_status,
			},
		)