# models/stock_rule.py
from odoo import models

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_stock_move_values(
        self, product_id, product_qty, product_uom, location_id,
        name, origin, company_id, values
    ):
        res = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # lote forzado
        forced_lot_id = values.get('lot_id')
        if forced_lot_id:
            res['so_lot_id'] = forced_lot_id
            res['lot_id']    = forced_lot_id

        # campos mármol + pedimento
        res.update({
            'marble_height':    values.get('marble_height', 0.0),
            'marble_width':     values.get('marble_width',  0.0),
            'marble_sqm':       values.get('marble_sqm',    0.0),
            'lot_general':      values.get('lot_general',   ''),
            'pedimento_number': values.get('pedimento_number', ''),
        })
        return res
