from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    oversell_digest_enabled = fields.Boolean(
        string='Enable Scheduled Digest Email',
        config_parameter='oversell_monitor.digest_enabled',
        default=False,
    )
    oversell_digest_frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'),
    ], string='Digest Frequency',
        config_parameter='oversell_monitor.digest_frequency',
        default='daily',
    )
    oversell_digest_recipient_ids = fields.Many2many(
        'res.partner',
        string='Digest Recipients',
        relation='oversell_digest_partner_rel',
    )
    oversell_global_min_threshold = fields.Float(
        string='Global Minimum Stock Threshold',
        config_parameter='oversell_monitor.global_min_threshold',
        default=0.0,
        help='Flag oversell risk when stock falls below this level (used when no product-specific threshold is set).',
    )
    oversell_auto_notify_customer = fields.Boolean(
        string='Auto-notify Customers on Oversell',
        config_parameter='oversell_monitor.auto_notify_customer',
        default=False,
    )
    oversell_auto_notify_vendor = fields.Boolean(
        string='Auto-notify Vendors on Oversell',
        config_parameter='oversell_monitor.auto_notify_vendor',
        default=False,
    )
