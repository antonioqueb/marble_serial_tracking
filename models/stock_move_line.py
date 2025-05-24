# models/stock_move_line.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # ─────────── Campos extendidos ───────────
    marble_height = fields.Float('Altura (m)')
    marble_width  = fields.Float('Ancho (m)')
    marble_sqm    = fields.Float('Metros Cuadrados')
    lot_general   = fields.Char('Lote General')
    bundle_code   = fields.Char('Bundle Code')

    # ─────────── Creación automática de lote ───────────
    @api.model_create_multi
    def create(self, vals_list):
        """
        Para recepciones (*incoming*):
        • Si viene `lot_general` y NO `lot_id`, se crea SIEMPRE un
          nuevo `stock.lot` secuencial (no se reutiliza ninguno),
          logrando nombres UYI-001, UYI-002, UYI-003…
        """
        lots_env = self.env['stock.lot']
        seq_env  = self.env['ir.sequence'].sudo()

        # 🔸 PRE-LOG
        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        # 1) Generar / asignar lote ANTES de super()
        for vals in vals_list:
            # ► Sólo si aún no hay lote y viene `lot_general`
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            bundle_code_val = vals.get('bundle_code')

            # ► Verificar que la línea pertenezca a un picking de entrada
            picking_code = vals.get('picking_code')  # cuando viene del escáner
            if not picking_code:
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                _logger.debug(
                    "[SML-CREATE] No es 'incoming' (code=%s) → sin lote auto",
                    picking_code
                )
                continue

            lot_general = vals['lot_general']
            product_id  = vals.get('product_id')

            # 1.1) Asegurar secuencia específica por `lot_general`
            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name':   _('Secuencia Mármol %s') % lot_general,
                    'code':   seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
                _logger.debug("[SEQ] Creada nueva secuencia %s", seq_code)

            # 1.2) Generar SIEMPRE un lote nuevo (no se reutiliza)
            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name':          lot_name,
                'product_id':    product_id,
                'company_id':    vals.get('company_id'),
                'marble_height': vals.get('marble_height'),
                'marble_width':  vals.get('marble_width'),
                'marble_sqm':    vals.get('marble_sqm'),
                'lot_general':   lot_general,
                'bundle_code':   bundle_code_val,
            }).id
           

        # 2) Crear las líneas normalmente
        move_lines = super().create(vals_list)

       
        return move_lines
