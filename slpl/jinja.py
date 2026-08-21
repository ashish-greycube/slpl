import frappe
import erpnext
import pyqrcode 

def get_qr_code(qr_text, scale=2):
	return pyqrcode.create(qr_text).png_as_base64_str(scale=scale, quiet_zone=1)


def get_table_data(item_data):
	# Groups Packing List items by box (unit), summing box-level dimensions/weight.
	# The first item of each box carries the totals + rowspan; the rest get rowspan 0,
	# so the print format only needs to render those columns when rowspan is truthy.
	if not item_data:
		return [], 0

	unique_boxes = []
	for item in item_data:
		if item.unit not in unique_boxes:
			unique_boxes.append(item.unit)
	unique_boxes.sort()

	data = []
	for box in unique_boxes:
		box_items = []
		total_gross = 0
		total_net = 0
		total_height = 0
		total_length = 0
		total_width = 0

		for pi in item_data:
			if pi.unit != box:
				continue

			total_gross += pi.gross
			total_net += pi.net
			total_height += pi.height
			total_length += pi.length
			total_width += pi.width

			box_items.append({
				"item_code": pi.item_code,
				"qty": pi.qty,
				"length": pi.length,
				"height": pi.height,
				"net": pi.net,
				"gross": pi.gross,
				"width": pi.width,
				"packaging_type": pi.packaging_type,
				"unit": pi.unit,
				"description": pi.description,
				"unit_count": pi.unit,
				"rowspan": 0,
			})

		box_items[0].update({
			"rowspan": len(box_items),
			"total_gross": total_gross,
			"total_net": total_net,
			"total_height": total_height,
			"total_length": total_length,
			"total_width": total_width,
		})
		data.extend(box_items)

	return data, len(unique_boxes)


def get_boxes(item_data):
	# One entry per box (unit), each with its packed items nested - used by
	# print formats that render one page/label per box (e.g. Box Wise Barcode).
	boxes = {}
	order = []

	for item in item_data or []:
		if item.unit not in boxes:
			boxes[item.unit] = {
				"unit": item.unit,
				"packaging_type": item.packaging_type,
				"total_qty": 0,
				"total_gross": 0,
				"total_net": 0,
				"packed_items": [],
			}
			order.append(item.unit)

		box = boxes[item.unit]
		box["total_qty"] += item.qty
		box["total_gross"] += item.gross
		box["total_net"] += item.net
		box["packed_items"].append(item)

	return [boxes[unit] for unit in sorted(order)]


def get_qr_table_text(plid, box):
	# Builds a fixed-width, aligned plain-text table (padded columns + divider
	# lines) so the QR content looks like a real table when scanned - QR codes
	# only carry plain text, so this is the closest thing to an HTML table.
	item_w, qty_w = 30, 5
	divider = "-" * (item_w + qty_w)

	lines = [
		"MWI Logistics Helpdesk",
		f"PLID: {plid}",
		divider,
		f"{'Item'.ljust(item_w)}{'Qty'.rjust(qty_w)}",
		divider,
	]

	for pi in box.get("packed_items", []):
		item_text = f"{pi.item_code or ''}".ljust(item_w-len(pi.item_code))
		qty = str(pi.qty or "").rjust(qty_w)
		lines.append(f"{item_text}{qty}")

	lines.append(divider)
	lines.append("Phone No: 0234039403948")

	return "\n".join(lines)


def get_company_address():
	default_company = erpnext.get_default_company()
	address_doc = frappe.get_doc("Address", {"address_title": default_company or "MECHWELL INDUSTRIES LIMITED"})
	HTML = f"""
		<p style="text-transform: uppercase; font-weight: bold; margin: 0;">{default_company}, {address_doc.city or ""}</p>
		<p>{address_doc.address_line1}<p>
		<p>{address_doc.address_line2 if address_doc.address_line2 else ""}, {address_doc.pincode}</p>
	"""
	return HTML