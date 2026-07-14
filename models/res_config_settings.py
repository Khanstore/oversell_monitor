from odoo import models, fields, api


class OversellSettings(models.TransientModel):
    """Dedicated settings model — completely separate from res.config.settings
    so it never interferes with General Settings."""
    _name = 'oversell.monitor.settings'
    _description = 'Oversell Monitor Settings'

    digest_enabled = fields.Boolean(
        string='Enable Scheduled Digest Email',
        default=lambda self: self._get_param('digest_enabled', False),
    )
    digest_frequency = fields.Selection([
        ('daily', 'Daily'), ('weekly', 'Weekly'),
    ], string='Digest Frequency',
        default=lambda self: self._get_param('digest_frequency', 'daily'),
    )
    global_min_threshold = fields.Float(
        string='Global Min Stock Threshold',
        default=lambda self: float(self._get_param('global_min_threshold', 0)),
        help='Flag oversell risk when stock falls below this quantity. 0 = disabled.',
    )
    auto_notify_vendor = fields.Boolean(
        string='Auto-notify Vendors on Oversell',
        default=lambda self: self._get_param('auto_notify_vendor', False),
    )
    auto_notify_customer = fields.Boolean(
        string='Auto-notify Customers on Oversell',
        default=lambda self: self._get_param('auto_notify_customer', False),
    )

    def _get_param(self, key, default=False):
        val = self.env['ir.config_parameter'].sudo().get_param(
            f'oversell_monitor.{key}')
        if val is False or val is None:
            return default
        if isinstance(default, bool):
            return val == 'True'
        return val

    def _set_param(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param(
            f'oversell_monitor.{key}', str(value))

    def action_save(self):
        self.ensure_one()
        self._set_param('digest_enabled', self.digest_enabled)
        self._set_param('digest_frequency', self.digest_frequency)
        self._set_param('global_min_threshold', self.global_min_threshold)
        self._set_param('auto_notify_vendor', self.auto_notify_vendor)
        self._set_param('auto_notify_customer', self.auto_notify_customer)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Settings Saved',
                'message': 'Oversell Monitor settings have been saved.',
                'type': 'success',
                'sticky': False,
            },
        }

    def action_discard(self):
        return {'type': 'ir.actions.act_window_close'}
