# models/stock_move_line.py
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    marble_height    = fields.Float('Altura (m)')
    marble_width     = fields.Float('Ancho (m)')
    marble_sqm       = fields.Float('Metros Cuadrados')
    lot_general      = fields.Char ('Lote General')
    pedimento_number = fields.Char ('Número de Pedimento', size=18)

    # (código de creación automática de lote sigue idéntico)
    # ... resto de tu método create sin cambios ...
