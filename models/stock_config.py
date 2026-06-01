from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    oversell_min_threshold = fields.Float(
        string='Oversell Alert Threshold',
        help='Alert if stock falls below this quantity. 0 = use global setting.',
        default=0.0,
    )


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    oversell_buffer = fields.Float(
        string='Oversell Buffer Qty',
        help='Extra buffer on top of min_qty to flag near-stockout oversell risk.',
        default=0.0,
    )
