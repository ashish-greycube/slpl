import frappe

# On save of Production Plan if Sales Order and Item Code is present, 
# fetch the Serial Numbers from Sales Order Item and set it in Production Plan Item
def on_save_fetch_serial_numbers(self, method=None):
    if self.po_items:
        for item in self.po_items:
            if item.sales_order and item.item_code:
                serial_nos = frappe.db.get_value(
                    "Sales Order Item", {
                        "parent": item.sales_order, 
                        "item_code": item.item_code
                    }, 
                    "custom_serial_no"
                )
                if serial_nos:
                    item.custom_serial_no = serial_nos

# On save of Work Order if Production Plan and Production Plan Item is present, 
# fetch the Serial Numbers from Production Plan Item and set it in Work Order Custom Setial No
def on_work_order_save_fetch_serial_numbers(self, method=None):
    if self.production_plan and self.production_plan_item:
        serial_no = frappe.db.get_value(
            "Production Plan Item",
            self.production_plan_item,
            "custom_serial_no"
        )
        if serial_no:
            frappe.db.set_value("Work Order", self.name, "custom_serial_no", serial_no)