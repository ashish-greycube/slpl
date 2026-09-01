// Copyright (c) 2026, GreyCube Technologies and contributors
// For license information, please see license.txt

const BOM_TREE_CATEGORY_INDICATOR = {
    "Finished Good": "green",
    "Sub-Assembly": "blue",
    "Bought Out": "orange"
};

const PACKING_LIST_SOURCE_TABLES = [
    "items",
    "additional_items"
];

frappe.ui.form.on("Supply List MW", {
    refresh(frm) {
        if (frm.doc.docstatus == 1) {
            setup_packing_list_button(frm);
        }
    },

    project(frm) {
        if (frm.doc.project) {
            frappe.db.get_value("Project", frm.doc.project, "sales_order").then((r) => {
                let sales_order = r.message && r.message.sales_order;
                if (!sales_order) {
                    frappe.throw("Sales Order is not assigned in Project <b>" + frm.doc.project + "</b>");
                }
                frm.set_value("sales_order", sales_order);
                frappe.db.get_value("Sales Order", sales_order, "customer").then((res) => {
                    if (res.message && res.message.customer) {
                        frm.set_value("client", res.message.customer);
                    }
                });
            });

            frappe.call({
                method: "slpl.slpl.doctype.supply_list_mw.supply_list_mw.get_finished_goods_of_sales_order_with_bom_items",
                args: { doc: frm.doc },
                freeze: true,
                freeze_message: __("Fetching Finished Goods..."),
                callback: (r) => {
                    if (r.message && r.message.name) {
                        // The method saves the doc, which may assign its real autoname
                        // (renaming it away from "new-supply-list-mw-..."), so route to
                        // whatever name it actually ended up with.
                        frappe.set_route("Form", frm.doctype, r.message.name);
                    }
                }
            });
        }
    },

    get_items(frm) {
        if (!frm.doc.bom) {
            frappe.msgprint(__("Please select a BOM first"));
            return;
        }
        frappe.call({
            method: "slpl.slpl.doctype.supply_list_mw.supply_list_mw.get_additional_items_of_bom",
            args: { bom: frm.doc.bom },
            callback(r) {
                if (r.message) {
                    frm.clear_table("additional_items");
                    r.message.forEach((item) => {
                        let row = frm.add_child("additional_items");
                        row.item_code = item.item_code;
                        row.quantity = item.quantity;
                        row.brand = item.brand;
                        row.description = item.description;
                    });
                    frm.refresh_field("additional_items");
                    lock_fully_delivered_rows(frm);
                    frm.save();
                }
            }
        });
    },

    refresh_bom_details(frm) {
        frm.call("get_tag_no_for_bom_details").then((r) => {
            if (!r.message) {
                return;
            }

            frm.refresh_field("bom_details");
            frm.refresh_field("items");
            lock_fully_delivered_rows(frm);

            if (r.message.found) {
                frappe.show_alert({
                    message: __("Tag No found for {0} row(s)", [r.message.found]),
                    indicator: "green"
                });
            }

            if (r.message.not_found) {
                frappe.show_alert({
                    message: __("Tag No not found for {0} row(s)", [r.message.not_found]),
                    indicator: "orange"
                });
            }
        });
    },

    refresh_items(frm) {
        frm.call("refresh_items").then(() => {
            frm.refresh_field("items");
            lock_fully_delivered_rows(frm);
            frappe.show_alert({ message: __("Items refreshed"), indicator: "green" });
        });
    }
});

frappe.ui.form.on("Supply List Finished Good BOM Detail MW", {
    fetch_bom(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.call("slpl.slpl.doctype.supply_list_mw.supply_list_mw.get_default_bom_of_finished_items_of_sales_order", {
            item: row.item
        }).then((res) => {
            row.bom = res.message;
            row.bom_status = "BOM Exist";
            frm.refresh_field("bom_details");
        });
    },

    show_bom_tree(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.bom) {
            frappe.msgprint(__("Please fetch/select a BOM first"));
            return;
        }
        frm.call("get_bom_tree", { bom: row.bom }).then((r) => {
            if (!r.message) {
                return;
            }
            let tree_html = `<div class="tree with-skeleton">${render_bom_tree_node(r.message, true)}</div>`;

            let grid_row = frm.fields_dict.bom_details.grid.grid_rows_by_docname[cdn];
            let field = grid_row && grid_row.get_field("bom_tree");
            if (field && field.$wrapper) {
                field.set_value(tree_html);
                bind_bom_tree_toggles(field.$wrapper);
            }
        });
    }
});

function render_bom_tree_node(node, is_root = false) {
    let has_children = node.children && node.children.length;
    let icon = has_children
        ? frappe.utils.icon("folder-open", "sm")
        : frappe.utils.icon("primitive-dot", "xs");
    let indicator = BOM_TREE_CATEGORY_INDICATOR[node.category] || "gray";

    let label = `${frappe.utils.escape_html(node.item_code)}
        ${node.item_name ? `<span class="text-muted"> (${frappe.utils.escape_html(node.item_name)})</span>` : ""}
        <span class="indicator-pill ${indicator}" style="margin-left: 8px;">
            ${frappe.utils.escape_html(node.category)}
        </span>
        <span class="indicator-pill gray no-indicator-dot" style="margin-left: 4px;">
            ${node.qty} ${frappe.utils.escape_html(node.uom || "")}
        </span>`;

    let tag = is_root ? "div" : "li";
    let html = `<${tag} class="tree-node">
        <span class="tree-link">
            <span class="${has_children ? "node-parent" : ""}">${icon}</span>
            <a class="tree-label">${label}</a>
        </span>`;

    if (has_children) {
        html += `<ul class="tree-children">`;
        node.children.forEach((child) => {
            html += render_bom_tree_node(child);
        });
        html += `</ul>`;
    }
    html += `</${tag}>`;
    return html;
}

function bind_bom_tree_toggles($wrapper) {
    $wrapper.find(".tree-children").show();
    $wrapper.find(".tree-link").on("click", function (e) {
        e.stopPropagation();
        let $children = $(this).parent().children(".tree-children");
        if (!$children.length) {
            return;
        }
        let expanded = $children.is(":visible");
        $children.toggle(!expanded);
        $(this)
            .find(".node-parent")
            .html(expanded ? frappe.utils.icon("folder-normal", "sm") : frappe.utils.icon("folder-open", "sm"));
    });
}

// Create Packing List (shown when a row is checked in Items / Additional Items)
function get_selected_packing_rows(frm) {
    return PACKING_LIST_SOURCE_TABLES.flatMap((fieldname) => {
        let grid = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].grid;
        return grid ? grid.get_selected_children() : [];
    });
}

function toggle_create_packing_list_button(frm) {
    frm.remove_custom_button(__("Create Packing List"));
    if (get_selected_packing_rows(frm).length) {
        frm.add_custom_button(__("Create Packing List"), () => open_create_packing_list_dialog(frm));
    }
}

function setup_packing_list_button(frm) {
    PACKING_LIST_SOURCE_TABLES.forEach((fieldname) => {
        let grid = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].grid;
        if (!grid) {
            return;
        }
        grid.wrapper.off("click.packing_list_toggle").on("click.packing_list_toggle", ".grid-row-check", () => {
            setTimeout(() => {
                lock_fully_delivered_rows(frm);
                toggle_create_packing_list_button(frm);
            }, 0);
        });
    });
    lock_fully_delivered_rows(frm);
    toggle_create_packing_list_button(frm);
}

function open_create_packing_list_dialog(frm) {
    let selected_rows = get_selected_packing_rows(frm);
    if (!selected_rows.length) {
        return;
    }

    let packing_rows = selected_rows.map((row) => {
        let original_qty = row.quantity || 0;
        let delivered_qty = row.delivered_qty || 0;
        let is_additional_item = 0
        if (row.doctype == "Supply List Additional Item Detail MW") {
            is_additional_item = 1
        }
        return {
            supply_row_name: row.name,
            item_code: row.item_code,
            original_qty: original_qty,
            delivered_qty: delivered_qty,
            remaining_qty: original_qty - delivered_qty,
            qty_to_transfer: original_qty - delivered_qty,
            is_additional_item: is_additional_item
        };
    });

    let dialog = new frappe.ui.Dialog({
        title: __("Create Packing List"),
        size: "large",
        fields: [
            {
                fieldname: "packing_rows",
                fieldtype: "Table",
                label: __("Items"),
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: false,
                fields: [
                    { fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Item Code"), read_only: 1, in_list_view: 1 },
                    { fieldname: "original_qty", fieldtype: "Float", label: __("Original Qty"), read_only: 1, in_list_view: 1 },
                    { fieldname: "delivered_qty", fieldtype: "Float", label: __("Delivered Qty"), read_only: 1, in_list_view: 1 },
                    { fieldname: "remaining_qty", fieldtype: "Float", label: __("Remaining Qty"), read_only: 1, in_list_view: 1 },
                    {
                        fieldname: "qty_to_transfer",
                        fieldtype: "Float",
                        label: __("Qty To Transfer"),
                        in_list_view: 1,
                    },
                    { fieldname: "supply_row_name", fieldtype: "Data", label: __("Supply Row Name"), hidden: 1 },
                    { fieldname: "is_additional_item", fieldtype: "Check", label: __("Is Additional Item"), hidden: 1 }
                ],
                data: packing_rows
            }
        ],
        primary_action_label: __("Create"),
        primary_action() {
            let rows = dialog.fields_dict.packing_rows.grid.get_data();

            let invalid_rows = get_invalid_packing_rows(rows);
            if (invalid_rows.length) {
                // Belt-and-braces: the Create button is disabled while any row is
                // invalid, but this still guards against e.g. an Enter-key submit.
                frappe.throw(
                    __("Qty To Transfer cannot be greater than Remaining Qty for item(s): {0}", [
                        invalid_rows.map((row) => row.item_code).join(", ")
                    ])
                );
            }

            // Stock availability can only be checked server-side (against the
            // warehouse configured in Mechwell Setting MW), so this call's
            // callback only fires once that also passes - frappe.throw() inside
            // it aborts silently (error dialog shown, callback never runs).
            frappe.call({
                method: "slpl.slpl.doctype.supply_list_mw.supply_list_mw.validate_stock_availability",
                args: {
                    items: rows.map((row) => ({ item_code: row.item_code, qty: row.qty_to_transfer }))
                },
                freeze: true,
                freeze_message: __("Checking stock availability..."),
                callback: () => {
                    dialog.hide();

                    let finished_good_row = selected_rows.find((row) => row.bom_details_item_row);
                    let bom_detail = finished_good_row
                        ? (frm.doc.bom_details || []).find((d) => d.name === finished_good_row.bom_details_item_row)
                        : null;

                    frappe.model.open_mapped_doc({
                        method: "slpl.slpl.doctype.supply_list_mw.supply_list_mw.make_packing_list",
                        frm: frm,
                        args: {
                            selected_items: JSON.stringify(
                                rows.map((row) => ({
                                    item_code: row.item_code,
                                    qty_to_pack: row.qty_to_transfer,
                                    supply_row_name: row.supply_row_name,
                                    is_additional_item: row.is_additional_item
                                }))
                            ),
                            product_name: bom_detail ? bom_detail.item : null,
                            quantity: bom_detail ? bom_detail.qty : null
                        }
                    });
                }
            });
        }
    });
    dialog.show();
}

function get_invalid_packing_rows(rows) {
    return rows.filter((row) => flt(row.qty_to_transfer) > flt(row.remaining_qty));
}

function lock_fully_delivered_rows(frm) {
    PACKING_LIST_SOURCE_TABLES.forEach((fieldname) => {
        let grid = frm.fields_dict[fieldname] && frm.fields_dict[fieldname].grid;
        if (!grid) {
            return;
        }
        (grid.grid_rows || []).forEach((grid_row) => {
            if (!grid_row.doc || !grid_row.wrapper) {
                return;
            }
            let is_fully_delivered = flt(grid_row.doc.delivered_percentage) >= 100;
            let $checkbox = grid_row.wrapper.find(".grid-row-check");
            $checkbox.prop("disabled", is_fully_delivered);
            if (is_fully_delivered && grid_row.doc.__checked) {
                grid_row.doc.__checked = 0;
                $checkbox.prop("checked", false);
            }
        });
    });
}