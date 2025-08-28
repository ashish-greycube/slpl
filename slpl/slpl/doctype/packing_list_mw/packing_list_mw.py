# Copyright (c) 2025, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form

class PackingListMW(Document):
	def on_submit(self):
		self.backport_supplied_qty_to_fl()

	def validate(self):
		self.calculate_unique_unit_count()
		self.get_qr_data()

	def backport_supplied_qty_to_fl(self):
		packing_items = self.packing_items
		fs_doc = frappe.get_doc('Final Supply MW', self.final_supply_reference)
		if len(packing_items) > 0:
			for pack_item in packing_items:
				for fs_item in fs_doc.items:
					if pack_item.item_code == fs_item.item_code:
						if ((fs_item.sales_order_item == self.product_name)) or (fs_item.sales_order_item == None):
							frappe.db.set_value(
								'Final Supply Item Details MW', 
								{
									'name' : fs_item.name
								},
								'shipped_qty',  
								fs_item.shipped_qty + pack_item.qty
							)

							frappe.db.set_value(
								'Final Supply Item Details MW', 
								{
									'name' : fs_item.name
								},
								'to_be_shipped',  
								fs_item.quantity - (fs_item.shipped_qty + pack_item.qty)
							)

							original_qty = frappe.db.get_value('Final Supply Item Details MW', fs_item.name, 'quantity') # fs_item.quantity
							shipped_qty = frappe.db.get_value('Final Supply Item Details MW', fs_item.name, 'shipped_qty') # fs_item.shipped_qty
							shipped_percentage = (shipped_qty * 100) / original_qty
							shipped_percentage = round(shipped_percentage, 2)

							frappe.db.set_value(
								'Final Supply Item Details MW', 
								{
									'name' : fs_item.name
								},
								'delivered_percentage',  
								shipped_percentage
							)
			frappe.msgprint("Quantities and Delivered Percentage is Updated in Supply List {0}".format(get_link_to_form('Final Supply MW', self.final_supply_reference)), alert=True)
	
	def calculate_unique_unit_count(self):
		if len(self.packing_items) > 0:
			unique_boxes = []
			unique_count = {}
			for item in self.packing_items:
				if item.unit not in unique_boxes:
					unique_boxes.append(item.unit)

			for box in unique_boxes:
				count = 0
				for item in self.packing_items:
					if item.unit == box:
						count = count + 1
				unique_count[box] = count
			
			for item in self.packing_items:
				item.unit_count = unique_count[item.unit]
			
	def get_qr_data(self):
		unique_boxes = []
		qr_data_by_boxes = []
		unique_boxes.append(self.packing_items[0].unit)

		

		if len(self.packing_items) > 0:
			for item in self.packing_items:
				if item.unit not in unique_boxes:
					unique_boxes.append(item.unit)
					
			unique_boxes.sort()
			print(unique_boxes)
			data = []
			
			for ub in unique_boxes:
				boxitems = []
				boxdict = {
					'box': ub,
				}
				for pi in self.packing_items:
					if pi.unit == ub:
						boxitems.append(pi)
				boxdict.update({
					'items' : boxitems,
					'rowspan' : len(boxitems)
				})
				data.append(boxdict)

			print(data)

			for box in unique_boxes:
				items = ""
				total_qty = 0
				for d in self.packing_items:
					if d.unit == box:
						items = items + "{0}\t\tQty: {1}\n".format(d.item_code, d.qty)
						total_qty = total_qty + d.qty
						packaging_type = d.packaging_type

				box_details = {
					'pl_id': "{0}-{1}".format(box, self.name),
					'box_no': box ,
					'items':  items,
					'packing_type' : packaging_type,
					'box_qty' : total_qty,
					'packing_list_id' : self.name
				}
				qr_data_by_boxes.append(box_details)

			return qr_data_by_boxes
		
		