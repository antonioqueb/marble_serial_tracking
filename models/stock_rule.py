# models/stock_rule.py
from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        """
        *Extendemos* la salida original para inyectar:
        • Lote forzado
        • Datos de mármol
        • Número de pedimento
        """
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # Lote forzado (si viene desde la venta)
        forced_lot = values.get('lot_id')
        if forced_lot:
            res['so_lot_id'] = forced_lot
            res['lot_id']    = forced_lot

        # Datos adicionales
        res.update({
            'marble_height':    values.get('marble_height', 0.0),
            'marble_width':     values.get('marble_width',  0.0),
            'marble_sqm':       values.get('marble_sqm',    0.0),
            'lot_general':      values.get('lot_general',   ''),
            'bundle_code':      values.get('bundle_code',   ''),
            'pedimento_number': values.get('pedimento_number', ''),
        })
        return res
