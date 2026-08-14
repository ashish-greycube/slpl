# Copyright (c) 2026, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SupplyListMW(Document):
	@frappe.whitelist()
	def get_default_bom_of_finished_items_of_sales_order(self):
		pass
