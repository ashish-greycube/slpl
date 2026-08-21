# Copyright (c) 2026, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


class CustomWorkOrder(WorkOrder):
	def create_serial_no_batch_no(self):
		if self.track_semi_finished_goods:
			return

		custom_serial_nos = self.get_custom_serial_no_list()
		if not custom_serial_nos:
			# No customer-provided serial numbers - fall back to the standard
			# has_serial_no/serial_no_series driven auto-generation.
			return super().create_serial_no_batch_no()

		# Customer-provided serial numbers always win, regardless of whether
		# the item itself is marked as serialized.
		self.validate_custom_serial_no(custom_serial_nos)

		if self.has_batch_no:
			self.create_batch_for_finished_good()

		self.create_serial_nos_from_custom_field(custom_serial_nos)

	def get_custom_serial_no_list(self):
		if not self.custom_serial_no:
			return []
		return [sn.strip() for sn in self.custom_serial_no.split(",") if sn.strip()]

	def validate_custom_serial_no(self, serial_nos):
		if len(serial_nos) != cint(self.qty):
			frappe.throw(
				_("Number of Serial Nos in {0} ({1}) does not match the Work Order Qty ({2})").format(
					frappe.bold("Serial NOs"), len(serial_nos), self.qty
				)
			)

		duplicates = {sn for sn in serial_nos if serial_nos.count(sn) > 1}
		if duplicates:
			frappe.throw(
				_("Duplicate Serial Nos in {0}: {1}").format(
					frappe.bold("Serial NOs"), ", ".join(sorted(duplicates))
				)
			)

		existing = frappe.get_all("Serial No", filters={"name": ["in", serial_nos]}, pluck="name")
		if existing:
			frappe.throw(
				_("Serial No(s) already exist: {0}").format(frappe.bold(", ".join(existing)))
			)

	def create_serial_nos_from_custom_field(self, serial_nos):
		item_details = frappe.get_cached_value(
			"Item", self.production_item, ["item_name", "description"], as_dict=True
		)

		for serial_no in serial_nos:
			frappe.get_doc({
				"doctype": "Serial No",
				"serial_no": serial_no,
				"item_code": self.production_item,
				"item_name": item_details.item_name,
				"description": item_details.description,
				"company": self.company,
				"work_order": self.name,
				"status": "Inactive",
			}).insert(ignore_permissions=True)
