# Copyright (c) 2025, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PackingListMW(Document):
	def on_submit(self):
		self.update_delivered_percentage_in_supply_list()

	def validate(self):
		self.set_unique_packing_units()
	
	def set_unique_packing_units(self):
		packing_units = []
		if self.packing_items:
			for item in self.packing_items:
				if item.unit and item.unit not in packing_units:
					packing_units.append(item.unit)
		self.total_units = len(packing_units) if packing_units != [] else 0
		
	def update_delivered_percentage_in_supply_list(self):
		if self.packing_items:
			for item in self.packing_items:
				if item.supply_row_name and item.is_additional_item:
					self.update_percentage("Supply List Additional Item Detail MW", item.qty, item.supply_row_name)
				else:
					self.update_percentage("Supply List Item Details MW", item.qty, item.supply_row_name)

	def update_percentage(self, doctype, qty, row):
		original_qty, previously_delivered_qty = frappe.db.get_value(doctype, row, ["quantity", "delivered_qty"]) or (0, 0)
								
		delivered_qty = previously_delivered_qty + qty
		remaining_qty = original_qty - delivered_qty
		delivered_percentage = round((delivered_qty / original_qty) * 100, 2)

		frappe.db.set_value(doctype, row, "delivered_qty", delivered_qty)
		frappe.db.set_value(doctype, row, "remaining_qty", remaining_qty)
		frappe.db.set_value(doctype, row, "delivered_percentage", delivered_percentage)