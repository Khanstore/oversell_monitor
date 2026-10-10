{
    'name': 'Oversell & Out-of-Stock Monitor',
    'version': '18.0.2.1.1',
    'category': 'Inventory/Inventory',
    'summary': 'Track, alert, and reorder oversold eCommerce products grouped by vendor and area',
    'description': """
Oversell & Out-of-Stock Monitor v2.1
====================================
Full-featured oversell management for Odoo 18 eCommerce:

- Live report: orders beyond available stock, grouped by vendor/area
- Date filters: today / last 7 days / this month / custom range
- One-click Purchase Order creation for deficit qty
- Email alerts to vendors and customers
- Oversell history log (permanent audit trail)
- Dashboard with top oversold products and vendor charts
- Restock ETA from open POs
- Delivery status column (backorder tracking)
- Minimum stock threshold warnings
- Scheduled daily/weekly digest email
- Warehouse-scoped free-stock reporting with reservation awareness
- Includes sent quotations in live shortage monitoring, while confirmed orders receive stock-allocation priority
- Outstanding demand allocation across orders, oldest first
- Configurable minimum-stock threshold in the live report
- Safer purchase-order wizard validation
- Configurable digest schedule and improved email handling
- Multi-company safeguards (requires deployment testing)
    """,
    'author': 'Custom',
    'depends': [
        'sale_management',
        'stock',
        'purchase',
        'website_sale',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_templates.xml',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/oversell_monitor_views.xml',
        'views/oversell_history_views.xml',
        'views/oversell_dashboard_views.xml',
        'wizard/create_po_wizard_views.xml',
        'wizard/send_alert_wizard_views.xml',
        'report/oversell_report.xml',
        'views/oversell_monitor_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'oversell_monitor/static/src/css/oversell_monitor.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
