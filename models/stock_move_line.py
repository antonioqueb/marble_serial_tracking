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

    # ─────────── Creación automática de lote ───────────
    @api.model_create_multi
    def create(self, vals_list):
        """
        Genera (o reutiliza) un stock.lot si:
        • La línea pertenece a una recepción (picking tipo *incoming*) y
        • Viene un valor para `lot_general` pero no `lot_id`.
        """
        lots_env   = self.env['stock.lot']
        seq_env    = self.env['ir.sequence'].sudo()

        # 🔸 PRE-LOG
        for vals in vals_list:
            _logger.debug("[SML-CREATE|PRE] vals=%s", vals)

        # 1) Lógica de lote antes de llamar a super()
        for vals in vals_list:
            # ► Solo si no hay lote aún y viene 'lot_general'
            if vals.get('lot_id') or not vals.get('lot_general'):
                continue

            # ► Determinar si la línea es de una recepción (incoming)
            #    Durante el create no existe aún move_line, usamos el contexto
            picking_code = vals.get('picking_code')  # cuando viene de scanner
            if not picking_code:
                # ⇒ Caso normal: obtenemos el move para checar su picking
                move = self.env['stock.move'].browse(vals.get('move_id'))
                picking_code = move.picking_type_id.code

            if picking_code != 'incoming':
                _logger.debug("[SML-CREATE] No es 'incoming' (code=%s) → sin lote", picking_code)
                continue

            lot_general = vals['lot_general']
            product_id  = vals.get('product_id')

            # 1.1) Reutilizar lote existente
            existing_lot = lots_env.search([
                ('product_id', '=', product_id),
                ('lot_general', '=', lot_general)
            ], limit=1)
            if existing_lot:
                vals['lot_id'] = existing_lot.id
                _logger.info("[LOT-AUTO] Reutilizado lote %s (ID %s) para producto %s",
                             existing_lot.name, existing_lot.id, product_id)
                continue

            # 1.2) Crear nuevo lote con secuencia específica
            seq_code = f"marble.serial.{lot_general}"
            sequence = seq_env.search([('code', '=', seq_code)], limit=1)
            if not sequence:
                sequence = seq_env.create({
                    'name': _('Secuencia Mármol %s') % lot_general,
                    'code': seq_code,
                    'padding': 3,
                    'prefix': f"{lot_general}-",
                })
                _logger.debug("[SEQ] Creada nueva secuencia %s", seq_code)

            lot_name = sequence.next_by_id()
            vals['lot_id'] = lots_env.create({
                'name':           lot_name,
                'product_id':     product_id,
                'company_id':     vals.get('company_id'),
                'marble_height':  vals.get('marble_height'),
                'marble_width':   vals.get('marble_width'),
                'marble_sqm':     vals.get('marble_sqm'),
                'lot_general':    lot_general,
            }).id
            _logger.info("[LOT-AUTO] Creado lote %s para producto %s (general=%s)",
                         lot_name, product_id, lot_general)

        # 2) Crear las líneas normalmente
        move_lines = super().create(vals_list)

        # 🔸 POST-LOG
        for line in move_lines:
            _logger.debug(
                "[SML-CREATE|POST] line_id=%s lot=%s height=%s width=%s sqm=%s",
                line.id, line.lot_id.name, line.marble_height, line.marble_width, line.marble_sqm
            )
        return move_lines
