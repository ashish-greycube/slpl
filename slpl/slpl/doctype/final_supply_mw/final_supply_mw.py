# Copyright (c) 2025, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.desk.treeview import get_children
from frappe.model.mapper import get_mapped_doc

class FinalSupplyMW(Document):
	@frappe.whitelist()
	def get_unique_so(self):
		so = self.sales_order
		so_doc = frappe.get_doc("Sales Order", so)
		so_array = []
		for item in so_doc.items:
			so_array.append(item.item_code)
		so_list = "\n".join(so_array)
		return so_list
	

@frappe.whitelist()
def get_dialog_table_data(so_item, docname):
	fs_items = []
	if docname != None:
		fs_doc = frappe.get_doc('Final Supply MW', docname)
		if fs_doc != None:
			for fs_item in fs_doc.items:
				if fs_item.sales_order_item == so_item or fs_item.sales_order_item == None:
					if fs_item.delivered_percentage < 100:
						fs_items.append({
							'item_code' : fs_item.item_code,
							'description' : fs_item.description,
							'qty' : fs_item.quantity,
							'so_name' : fs_item.sales_order_item,
							'shipped_qty' : fs_item.shipped_qty,
							'tobe_qty' : fs_item.quantity - fs_item.shipped_qty
						})
			return fs_items


# Function For Default BOM Of So Items
@frappe.whitelist()
def get_default_bom(so):
	default_boms = []
	if so != None:
		sales_order_doc = frappe.get_doc('Sales Order', so)
		
		if sales_order_doc != None:
			for soitem in sales_order_doc.items:
				if soitem.item_group != "FINISH GOODS":
					default_boms.append({
						'item' : soitem.item_code,
					})
					frappe.msgprint("Item {0} Does Not Have Default BOM".format(get_link_to_form("Item", frappe.bold(soitem.item_code))), alert=True, indicator='red')
				elif soitem.item_group == 'FINISH GOODS':
					bom = frappe.db.get_value("Item", soitem.item_code, 'default_bom')
					if bom != None:
						default_boms.append({
							'item' : soitem.item_code,
							'default_bom' : bom
						})
						
	return default_boms

@frappe.whitelist()
def get_items_data(doc, so):
	doc = frappe.parse_json(doc)
	if so != None:
		fsitems = []
		data = []
		sales_order = frappe.get_doc("Sales Order", so)

		if sales_order != None:
			for so_item in sales_order.items:

				# If Group != Finish Goods Then Just Append This As It Is.
				if so_item.item_group != "FINISH GOODS":
					fsitems.append({
						'item_code': so_item.item_code,
						'description' : so_item.description,
						'brand' : frappe.db.get_value('Item', so_item.item_code, 'brand') if not None else '',
						'qty' : so_item.qty,
						'so_item' : so_item.item_code
					})

				# If Item Group Is Finish Goods Then Find BOM No
				elif so_item.item_group == "FINISH GOODS":

					# Take Default BOM For that Item 
					bom = frappe.db.get_value("Item", so_item.item_code, 'default_bom')
					
					# Once Get Bom Then Take Item Which Has Level 0 Or Item Group Boughtout
					if bom != [] or None:
						bom_doc = frappe.get_doc('BOM', bom)
						for item in bom_doc.items:
							# Taking All The Level 0 Items
							if item.parent == bom_doc.name:
								row = {
									'item_code': item.item_code,
									'description' : item.description,
									'brand' : frappe.db.get_value('Item', so_item.item_code, 'brand') if not None else '',
									'qty' : item.qty * so_item.qty,
									'so_item' : so_item.item_code
								}
								fsitems.append(row)
								data.append(row)
							if item.bom_no != "" or None:
								get_bought_out_items(item.bom_no, fsitems, so_item)
	
	for fsitem in fsitems:
		isPresent = False
		for d in data:
			if d['item_code'] == fsitem['item_code'] and 'so_item' not in fsitem:
				d['qty'] = d['qty'] + fsitem['qty']
				isPresent =True
				
		if isPresent != True and (('so_item' not in fsitem) or ('so_item'in fsitem and fsitem['so_item'] == None)):
			data.append(fsitem)
	return data

# Recursive Function For Checking Boughtout Items
def get_bought_out_items(bom, fsitems, so_item):
	# List Of Item Groups 
	main = get_children('Item Group', "BOUGHTOUT")
	groups = ["BOUGHTOUT"]
	for a in main:
		groups.append(a['value'])
		childs = get_children("Item Group", a['value'])
		for c in childs:
			groups.append(c['value'])	

	bom_doc = frappe.get_doc('BOM', bom)
	for item in bom_doc.items:
		if item.bom_no != "" or None:
			get_bought_out_items(item.bom_no, fsitems, so_item)
		else:
			bom_item_group = frappe.db.get_value('Item', item.item_code, 'item_group')
			if bom_item_group in groups:
				row = {
					'item_code': item.item_code,
					'description' : item.description,
					'brand' : frappe.db.get_value('Item', so_item.item_code, 'brand') if not None else '',
					'qty' : item.qty * bom_doc.quantity ,
				}
				
				fsitems.append(row)

# Function For Opening Packing List 
@frappe.whitelist()
def make_packing_list(source_name, target_doc=None, item_code=None, item_data=None):
	item_data = frappe.parse_json(item_data)
	for item in item_data:
		if item['shipped_qty'] + item['tobe_qty'] > item['qty']:
			frappe.throw('Item qty being shipped for item {0} is more than total qty'.format(item['item_code'])) 


	def set_missing_values(source, target):
		target.product_name = item_code
		target.quantity = frappe.db.get_value('Sales Order Item', { 'parent' : source.sales_order, 'item_code' : item_code }, 'qty')
		target.ack_no = source.project
		destination = frappe.db.get_value('Sales Order', source.sales_order, 'address_display')
		target.destination = destination.replace('<br>', '\n')
		target.final_supply_reference = source.name
		delivery_note = frappe.db.get_value("Delivery Note Item", {'against_sales_order' : source.sales_order}, 'parent')
		if delivery_note != None:
			target.delivery_note = delivery_note
			
		for item in item_data:
			target.append(
				'packing_items',
				{
					'item_code' : item['item_code'],
					'description' : item['description'],
					'qty' : item['tobe_qty']
				}
			)

	doc = get_mapped_doc(
		"Final Supply MW",
		source_name,
		{
			"Final Supply MW" : {
				"doctype": "Packing List MW",
				"field_map": {
					'product_name' : item_code,
					'packing_items' : item_data,
				}
			}
		},
		target_doc,
		set_missing_values
	)
	doc.save(ignore_permissions=True)
	return doc.name