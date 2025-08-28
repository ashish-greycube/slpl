// Copyright (c) 2025, GreyCube Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Final Supply MW", {
    project: function(frm) {
        frappe.db.get_value("Project", frm.doc.project, 'sales_order')
        .then(res => {
            if (res.message.sales_order == null) {
                frappe.msgprint({
                    message: "Sales Order Is Not Assigned In Selected Project!",
                    indicator: 'red'
                })
            }
        })
    },

    setup: function(frm) {
        frm.get_field("items").grid.cannot_add_rows = true;
        frm.get_field("items_bom_list").grid.cannot_add_rows = true;
        frappe.db.get_single_value('Mechwell Setting MW', 'permitted_role_for_supply_list').then(res => {
            for (let ur in frappe.user_roles) {
                if (frappe.user_roles[ur] == res) {
                    frm.get_field("items").grid.cannot_add_rows = false;
                    frm.get_field("items_bom_list").grid.cannot_add_rows = false;    
                }   
            }
        });
    },  

    sales_order: function (frm) {
        if (frm.doc.sales_order != null) {
            frappe.call({
                method: 'slpl.slpl.doctype.final_supply_mw.final_supply_mw.get_default_bom',
                args: {
                    'doc': frm.doc,
                    'so': frm.doc.sales_order
                },
                callback: function (res) {
                    data = res.message
                    frm.doc.items_bom_list = []
                    for (let d in data) {
                        let row = frm.add_child('items_bom_list', {
                            'item': data[d]['item'],
                            'default_bom': data[d]['default_bom']
                        })
                    }
                    frm.refresh_field('items_bom_list');
                }
            })

            frappe.call({
                method: 'slpl.slpl.doctype.final_supply_mw.final_supply_mw.get_items_data',
                args: {
                    'doc': frm.doc,
                    'so': frm.doc.sales_order
                },
                callback: function (result) {
                    data = result.message
                    frm.doc.items = []
                    for (d in data) {
                        let row = frm.add_child('items', {
                            'item_code': data[d]['item_code'],
                            'description': data[d]['description'],
                            'quantity': data[d]['qty'],
                            'brand': data[d]['brand'],
                            'sales_order_item': data[d]['so_item']
                        })
                    }
                    frm.refresh_field('items');
                }
            })
        }
    },

    refresh: function (frm) {
        if (frm.doc.docstatus == 1) {
            let dialog
            const dialog_fields = []

            let table_fields = [
                {
                    fieldtype: "Link",
                    fieldname: "item_code",
                    options: "Item",
                    label: __("Item"),
                    read_only: 1,
                    in_list_view: 1,
                    columns: 2
                },
                {
                    fieldtype: "Data",
                    fieldname: "description",
                    label: __("Description"),
                    read_only: 1,
                    in_list_view: 1,
                    columns: 2
                },
                {
                    fieldtype: "Float",
                    fieldname: "qty",
                    label: __("Qty"),
                    read_only: 1,
                    in_list_view: 1,
                    columns: 2
                },
                {
                    fieldtype: "Float",
                    fieldname: "shipped_qty",
                    label: __("Shipped Qty"),
                    read_only: 1,
                    in_list_view: 1,
                    columns: 2
                },
                {
                    fieldtype: "Float",
                    fieldname: "tobe_qty",
                    label: __("To Be Shipped"),
                    read_only: 0,
                    in_list_view: 1,
                    columns: 2
                }
            ];

            let table_item_field = {
                label: "Item Details",
                fieldname: "item_details",
                fieldtype: "Table",
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: false,
                reqd: 1,
                data: [],
                get_data: () => {
                    return [];
                },
                fields: table_fields
            }

            frm.call({
                method: 'get_unique_so',
                doc: frm.doc
            }).then(r => {
                let unique_so = r.message

                let item_field = {
                    fieldtype: 'Select',
                    fieldname: 'item_field',
                    label: __('Finish Good Item'),
                    options: unique_so,
                    reqd: 1,
                    onchange: function () {
                        frappe.call({
                            method: 'slpl.slpl.doctype.final_supply_mw.final_supply_mw.get_dialog_table_data',
                            args: {
                                so_item: dialog.get_field("item_field").value,
                                docname: frm.doc.name
                            },
                            callback: function (response) {
                                let item_list = response.message
                                let dialog_items = dialog.fields_dict.item_details;
                                dialog_items.df.data = []
                                dialog_items.grid.refresh();
                                if (item_list.length > 0) {
                                    item_list.forEach(element => {
                                        dialog_items.df.data.push(element);
                                        dialog_items.grid.refresh();
                                    });
                                }
                                dialog_items.grid.refresh()
                            }
                        })
                    }
                }
                dialog_fields.push(item_field);
                dialog_fields.push(table_item_field);
            })

            frm.add_custom_button('Make Packing List', function (frm) {
                dialog = new frappe.ui.Dialog({
                    title: __('Item Details'),
                    fields: dialog_fields,
                    primary_action_label: 'Create Packing List',
                    primary_action: function (values) {
                        frappe.call({
                            method: "slpl.slpl.doctype.final_supply_mw.final_supply_mw.make_packing_list",
                            args: {
                                'source_name': cur_frm.doc.name,
                                'target_doc': undefined,
                                'item_code': values.item_field,
                                'item_data': dialog.fields_dict.item_details.grid.get_selected_children(),
                            },
                            callback: function (response) {
                                console.log(response)
                                if (response.message) {
                                    frappe.open_in_new_tab = true;
                                    frappe.set_route("Form", "Packing List MW", response.message)
                                }
                            }
                        })

                        dialog.fields_dict.item_details.df.data = []
                        dialog.hide();
                    }
                })
                dialog.show();
            })
        }
    },
});