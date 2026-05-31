{
    'name': 'Oversell & Out-of-Stock Monitor',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Track oversold and out-of-stock eCommerce orders grouped by vendor and area',
    'description': """
Oversell & Out-of-Stock Monitor
================================
- Lists orders where products were sold beyond available stock (continue selling enabled)
- Filters by Today / This Week / Custom date range
- Groups by vendor and vendor area/region
- Shows current stock, ordered qty, deficit, average cost, last purchase cost
- Accessible from Inventory and Sales menus
    """,
    'author': 'Custom',
    'depends': ['sale_management', 'stock', 'purchase', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/oversell_monitor_views.xml',
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
