import frappe

def after_migrate():
    custom_fields = {
        "Sales Order Item" : [
            dict(
                is_custom_field=1,
                is_system_generated=0,
                fieldtype="Column Break",
                fieldname="custom_column_break_mfg",
                insert_after="bom_no"
            ),
            dict(
                is_custom_field=1,
                is_system_generated=0,
                label="Serial NOs",
                fieldtype="Small Text",
                fieldname="custom_serial_no",
                insert_after="custom_column_break_mfg",
                description="Please add comma(,) separated serial numbers for the items in this field. For example, SN001, SN002, SN003"
            ),
        ],

        "Production Plan Item" : [
            dict(
                is_custom_field=1,
                is_system_generated=0,
                label="Serial NOs",
                fieldtype="Small Text",
                fieldname="custom_serial_no",
                insert_after="sales_order_item",
                description="Please add comma(,) separated serial numbers for the items in this field. For example, SN001, SN002, SN003"
            ),
        ],

        "Work Order" : [
            dict(
                is_custom_field=1,
                is_system_generated=0,
                label="Serial NOs",
                fieldtype="Small Text",
                fieldname="custom_serial_no",
                insert_after="batch_size",
                description="Please add comma(,) separated serial numbers for the items in this field. For example, SN001, SN002, SN003"
            ),
        ]
    }

    print("Adding Custom Fields In Core Doctypes.....")
    for dt, fields in custom_fields.items():
        print("********************\n %s: " % dt, [d.get("fieldname") for d in fields])
    frappe.custom.doctype.custom_field.custom_field.create_custom_fields(custom_fields)