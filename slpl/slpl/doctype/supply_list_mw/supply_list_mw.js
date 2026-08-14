// Copyright (c) 2026, GreyCube Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supply List MW", {
    project(frm) {
        frappe.db.get_value("Project", frm.doc.project, 'sales_order')
            .then(res => {
                if (res.message.sales_order == null) {
                    frappe.msgprint({
                        message: `Sales Order is not assigned in Project <b>${frm.doc.project}</b>`,
                        indicator: 'red'
                    })
                }
            })
    },

    sales_order(frm) {
        if (frm.doc.sales_order) {
            frappe.db.get_doc("Sales Order", frm.doc.sales_order)
                .then((doc) => {
                    if (doc) {
                        for (let item in doc.items) {
                            frm.add_child("bom_details", {
                                "item": doc.items[item].item_code
                            })
                        }
                        frm.refresh_field("bom_details")
                    }
                })
        }
    }
});

frappe.ui.form.on("Supply List Finished Good BOM Detail MW", {
    fetch_bom(frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        frm.call("get_default_bom_of_finished_items_of_sales_order")
    }
})