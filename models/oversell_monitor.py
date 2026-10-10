from odoo import models, fields, tools


class OversellMonitorLine(models.Model):
    _name = 'oversell.monitor.line'
    _description = 'Oversell / Out-of-Stock Monitor Line'
    _auto = False
    _order = 'order_date desc, vendor_name, product_name'

    order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    order_name = fields.Char(string='Order', readonly=True)
    order_date = fields.Date(string='Order Date', readonly=True)
    order_state = fields.Selection([
        ('draft', 'Quotation'), ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'), ('done', 'Locked'), ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_name = fields.Char(string='Product Name', readonly=True)
    default_code = fields.Char(string='SKU', readonly=True)
    ordered_qty = fields.Float(string='Outstanding Qty', digits='Product Unit of Measure', readonly=True)
    qty_on_hand = fields.Float(string='Free Stock', digits='Product Unit of Measure', readonly=True)
    deficit_qty = fields.Float(string='Deficit', digits='Product Unit of Measure', readonly=True)
    min_qty_threshold = fields.Float(string='Min Threshold', readonly=True)
    avg_cost = fields.Float(string='Avg Cost', digits='Product Price', readonly=True)
    last_purchase_price = fields.Float(string='Last Purchase Cost', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    vendor_name = fields.Char(string='Vendor', readonly=True)
    vendor_area = fields.Char(string='Area / Region', readonly=True)
    restock_eta = fields.Date(string='Restock ETA', readonly=True)
    open_po_id = fields.Many2one('purchase.order', string='Open PO', readonly=True)
    delivery_status = fields.Char(string='Delivery Status', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Delivery Order', readonly=True)

    def init(self):
        """Build a live report using free stock in the sales order warehouse.

        Demand is converted to the product's default UoM and allocated oldest
        first within each company/warehouse/product bucket. This avoids
        counting the same available stock independently against every order.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH global_setting AS (
                    SELECT COALESCE(
                        NULLIF(value, '')::numeric, 0
                    ) AS min_threshold
                    FROM ir_config_parameter
                    WHERE key = 'oversell_monitor.global_min_threshold'
                    LIMIT 1
                ),
                free_stock AS (
                    SELECT
                        sw.id AS warehouse_id,
                        sw.company_id,
                        sq.product_id,
                        SUM(sq.quantity - sq.reserved_quantity) AS free_qty
                    FROM stock_warehouse sw
                    JOIN stock_location root ON root.id = sw.lot_stock_id
                    JOIN stock_location sl
                      ON sl.usage = 'internal'
                     AND sl.parent_path LIKE root.parent_path || '%%'
                    JOIN stock_quant sq
                      ON sq.location_id = sl.id
                     AND sq.company_id = sw.company_id
                    GROUP BY sw.id, sw.company_id, sq.product_id
                ),
                demand AS (
                    SELECT
                        sol.id,
                        so.id AS order_id,
                        so.name AS order_name,
                        so.date_order::date AS order_date,
                        so.state AS order_state,
                        so.company_id,
                        so.warehouse_id,
                        pp.id AS product_id,
                        pt.name->>'en_US' AS product_name,
                        pt.default_code,
                        GREATEST(sol.product_uom_qty - COALESCE(sol.qty_delivered, 0), 0)
                          * COALESCE(line_uom.factor, 1)
                          / NULLIF(COALESCE(product_uom.factor, 1), 0) AS open_qty,
                        COALESCE(fs.free_qty, 0) AS free_qty,
                        GREATEST(
                            COALESCE(pt.oversell_min_threshold, 0),
                            COALESCE(orp.product_min_qty, 0),
                            COALESCE((SELECT min_threshold FROM global_setting), 0)
                        ) AS min_threshold,
                        COALESCE((pp.standard_price->>so.company_id::text)::numeric,
                                 (pp.standard_price->>'1')::numeric, 0) AS avg_cost,
                        rc.id AS currency_id,
                        vendor.partner_id AS vendor_id,
                        COALESCE(rp.name, 'Unknown') AS vendor_name,
                        COALESCE(rp.city, state.name, 'Unknown') AS vendor_area,
                        last_po.price_unit AS last_purchase_price,
                        open_po.date_planned::date AS restock_eta,
                        open_po.po_id AS open_po_id,
                        COALESCE(picking.state, 'none') AS delivery_status,
                        picking.id AS picking_id,
                        SUM(
                            GREATEST(sol.product_uom_qty - COALESCE(sol.qty_delivered, 0), 0)
                            * COALESCE(line_uom.factor, 1)
                            / NULLIF(COALESCE(product_uom.factor, 1), 0)
                        ) OVER (
                            PARTITION BY so.company_id, so.warehouse_id, pp.id
                            ORDER BY
                                CASE WHEN so.state IN ('sale', 'done') THEN 0 ELSE 1 END,
                                so.date_order, so.id, sol.id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        ) AS cumulative_demand
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    JOIN product_product pp ON pp.id = sol.product_id
                    JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    JOIN uom_uom line_uom ON line_uom.id = sol.product_uom
                    JOIN uom_uom product_uom ON product_uom.id = pt.uom_id
                    LEFT JOIN free_stock fs
                      ON fs.product_id = pp.id
                     AND fs.company_id = so.company_id
                     AND fs.warehouse_id = so.warehouse_id
                    LEFT JOIN stock_warehouse_orderpoint orp
                      ON orp.product_id = pp.id
                     AND orp.company_id = so.company_id
                     AND (orp.location_id = (SELECT lot_stock_id FROM stock_warehouse WHERE id = so.warehouse_id)
                          OR orp.location_id IS NULL)
                    LEFT JOIN res_company company ON company.id = so.company_id
                    LEFT JOIN res_currency rc ON rc.id = company.currency_id
                    LEFT JOIN LATERAL (
                        SELECT psi.partner_id
                        FROM product_supplierinfo psi
                        WHERE psi.product_tmpl_id = pt.id
                          AND (psi.company_id IS NULL OR psi.company_id = so.company_id)
                        ORDER BY psi.sequence, psi.id
                        LIMIT 1
                    ) vendor ON TRUE
                    LEFT JOIN res_partner rp ON rp.id = vendor.partner_id
                    LEFT JOIN res_country_state state ON state.id = rp.state_id
                    LEFT JOIN LATERAL (
                        SELECT pol.price_unit
                        FROM purchase_order_line pol
                        JOIN purchase_order po ON po.id = pol.order_id
                        WHERE pol.product_id = pp.id
                          AND po.company_id = so.company_id
                          AND po.state IN ('purchase', 'done')
                        ORDER BY po.date_approve DESC NULLS LAST, po.id DESC
                        LIMIT 1
                    ) last_po ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT pol.date_planned, po.id AS po_id
                        FROM purchase_order_line pol
                        JOIN purchase_order po ON po.id = pol.order_id
                        WHERE pol.product_id = pp.id
                          AND po.company_id = so.company_id
                          AND po.state IN ('purchase', 'draft', 'sent')
                          AND pol.date_planned IS NOT NULL
                        ORDER BY pol.date_planned ASC, po.id
                        LIMIT 1
                    ) open_po ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT sp.id, sp.state
                        FROM stock_picking sp
                        WHERE sp.sale_id = so.id
                          AND sp.picking_type_id IN (
                              SELECT spt.id FROM stock_picking_type spt
                              WHERE spt.code = 'outgoing'
                          )
                        ORDER BY sp.id DESC
                        LIMIT 1
                    ) picking ON TRUE
                    WHERE so.state IN ('sent', 'sale', 'done')
                      AND so.warehouse_id IS NOT NULL
                      AND sol.product_id IS NOT NULL
                      AND pt.type != 'service'
                      AND GREATEST(sol.product_uom_qty - COALESCE(sol.qty_delivered, 0), 0) > 0
                ),
                allocated AS (
                    SELECT demand.*,
                        GREATEST(demand.cumulative_demand - demand.open_qty - demand.free_qty, 0) AS prior_shortage,
                        GREATEST(demand.cumulative_demand - demand.free_qty, 0) AS total_shortage
                    FROM demand
                )
                SELECT
                    id,
                    order_id,
                    order_name,
                    order_date,
                    order_state,
                    company_id,
                    warehouse_id,
                    product_id,
                    product_name,
                    default_code,
                    open_qty AS ordered_qty,
                    free_qty AS qty_on_hand,
                    GREATEST(total_shortage - prior_shortage, 0) AS deficit_qty,
                    min_threshold AS min_qty_threshold,
                    avg_cost,
                    COALESCE(last_purchase_price, 0) AS last_purchase_price,
                    currency_id,
                    vendor_id,
                    vendor_name,
                    vendor_area,
                    restock_eta,
                    open_po_id,
                    delivery_status,
                    picking_id
                FROM allocated
                WHERE total_shortage > prior_shortage
                   OR free_qty <= min_threshold
            )
        """ % self._table)

    def action_create_po(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Purchase Order',
            'res_model': 'oversell.create.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'active_model': 'oversell.monitor.line',
            },
        }

    def action_send_vendor_alert(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Vendor Alert',
            'res_model': 'oversell.send.alert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': [(0, 0, {
                    'product_id': rec.product_id.id,
                    'vendor_id': rec.vendor_id.id if rec.vendor_id else False,
                    'deficit_qty': rec.deficit_qty,
                    'order_id': rec.order_id.id,
                }) for rec in self],
            },
        }

    def action_view_purchase_history(self):
        """Open all confirmed PO lines for this product."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Purchase History — {self.product_name}',
            'res_model': 'purchase.order.line',
            'view_mode': 'list,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ],
            'context': {'search_default_groupby_partner': 1},
        }
