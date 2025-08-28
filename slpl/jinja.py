import frappe
import pyqrcode 

def get_qr_code(qr_text, scale=2):
	return pyqrcode.create(qr_text).png_as_base64_str(scale=scale, quiet_zone=1)

def get_qr_data(item_data, doc):
	# if len(item_data) > 0:
	# 	curr_unit = item_data[0].unit
	# 	unique_box_qr_data = []
	# 	items=""
	# 	total_qty = 0

	# 	for d in item_data:
	# 		if d.unit != curr_unit:
	# 			box_dict = {
	# 				'pl_id': "{0}-{1}".format(curr_unit, doc.name),
	# 				'box_no': curr_unit ,
	# 				'items':  items,
	# 				'packing_list' : doc.name,
	# 				'total_qty': total_qty,
	# 				'packaging_type' : package_type
	# 			}
	# 			unique_box_qr_data.append(box_dict)
	# 			items = ""
	# 			total_qty = 0
	# 			items = items + "{0}\t\tQty: {1}\n".format(d.item_code, d.qty)
	# 			package_type = d.packaging_type
	# 			total_qty = total_qty + d.qty
	# 			curr_unit = d.unit
	# 		elif curr_unit == d.unit:
	# 			items = items + "{0}\t\tQty: {1}\n".format(d.item_code, d.qty)
	# 			total_qty = total_qty + d.qty
	# 			package_type = d.packaging_type
	# 	box_dict = {
	# 		'pl_id': "{0}-{1}".format(curr_unit, doc.name),
	# 		'box_no': curr_unit ,
	# 		'items':  items,
	# 		'packing_list' : doc.name,
	# 		'total_qty': total_qty,
	# 		'packaging_type' : package_type
	# 	}		
	# 	unique_box_qr_data.append(box_dict)
	# 	print(unique_box_qr_data)
	# 	return unique_box_qr_data
			
	unique_boxes = []
	qr_data_by_boxes = []
	if len(item_data) > 0:
		unique_boxes.append(item_data[0].unit)
		for item in item_data:
			if item.unit not in unique_boxes:
				unique_boxes.append(item.unit)
		unique_boxes.sort()

		for box in unique_boxes:
			items = ""
			total_qty = 0
			for d in item_data:
				if d.unit == box:
					items = items + "{0}\t\tQty: {1}\n".format(d.item_code, d.qty)
					total_qty = total_qty + d.qty
					packaging_type = d.packaging_type

			box_details = {
				'pl_id': "{0}-{1}".format(box, doc.name),
				'box_no': box ,
				'items':  items,
				'packing_type' : packaging_type,
				'box_qty' : total_qty,
				'packing_list_id' : doc.name
			}
			qr_data_by_boxes.append(box_details)

	return qr_data_by_boxes


def get_table_data(item_data):
	unique_boxes = []
	unique_boxes.append(item_data[0].unit)
	data = []
	if len(item_data) > 0:
		for item in item_data:
			if item.unit not in unique_boxes:
				unique_boxes.append(item.unit)
		unique_boxes.sort()

		for ub in unique_boxes:
			boxitems = []
			total_gross = 0
			total_net = 0
			total_height = 0
			total_length = 0
			total_width = 0
			boxdict = {
				'box': ub,
			}

			for pi in item_data:
				if pi.unit == ub:
					total_gross = total_gross + pi.gross
					total_net = total_net + pi.net
					total_height = total_height + pi.height
					total_length = total_length + pi.length
					total_width = total_width + pi.width
					boxitems.append({
						'item_code' : pi.item_code,
						'qty': pi.qty,
						'length': pi.length,
						'height' : pi.height,
						'net' : pi.net,
						'gross' : pi.gross,
						'width' : pi.width,
						'packaging_type' : pi.packaging_type,
						'unit' : pi.unit,
						'description' : pi.description,
						'unit_count' : pi.unit_count,
						'rowspan' : 0
					})
			boxitems[0].update({
				'rowspan' : len(boxitems),
				'total_gross': total_gross,
				'total_net':total_net,
				'total_height':total_height,
				'total_length' :total_length,
				'total_width': total_width,
			}) 
			# boxdict.update({
			# 	'items' : boxitems,
			# 	'rowspan' : len(boxitems)
			# })
			for bi in boxitems:
				data.append(bi)

		return data, len(unique_boxes)