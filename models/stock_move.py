# models/stock_move.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # Campos de tracking desde la venta
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')

    # Campos de mármol
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('Metros Cuadrados')
    lot_general = fields.Char('Lote General')
    bundle_code = fields.Char('Bundle Code')
    marble_thickness = fields.Float('Grosor (cm)')

    # Campo computado para distinguir entregas
    is_outgoing = fields.Boolean(
        string='Es Salida',
        compute='_compute_is_outgoing',
        store=True
    )

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    def write(self, vals):
        lots_env = self.env['stock.lot']
        seq_env = self.env['ir.sequence'].sudo()

        res = super().write(vals)

        if 'lot_general' in vals and vals['lot_general']:
            for move in self:
                picking_code = move.picking_type_id.code
                if picking_code != 'incoming':
                    continue

                lot_general = vals['lot_general']
                product_id = move.product_id.id

                seq_code = f"marble.serial.{lot_general}"
                sequence = seq_env.search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = seq_env.create({
                        'name': _('Secuencia Mármol %s') % lot_general,
                        'code': seq_code,
                        'padding': 3,
                        'prefix': f"{lot_general}-",
                    })

                lot_name = sequence.next_by_id()
                lot_vals = {
                    'name': lot_name,
                    'product_id': product_id,
                    'company_id': move.company_id.id,
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': lot_general,
                    'bundle_code': move.bundle_code,
                    'marble_thickness': move.marble_thickness,
                }
                new_lot = lots_env.create(lot_vals)

                # Actualizar o crear move line asociada
                move_line = move.move_line_ids.filtered(lambda ml: not ml.lot_id)
                if move_line:
                    move_line.write({'lot_id': new_lot.id})
                else:
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'picking_id': move.picking_id.id,
                        'company_id': move.company_id.id,
                        'lot_id': new_lot.id,
                        'quantity': move.product_uom_qty,
                        'marble_height': move.marble_height,
                        'marble_width': move.marble_width,
                        'marble_sqm': move.marble_sqm,
                        'lot_general': lot_general,
                        'bundle_code': move.bundle_code,
                        'marble_thickness': move.marble_thickness,
                    })

        return res

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)

        if self.lot_id:
            vals['lot_id'] = self.lot_id.id

        vals.update({
            'marble_height': self.marble_height,
            'marble_width': self.marble_width,
            'marble_sqm': self.marble_sqm,
            'lot_general': self.lot_general,
            'bundle_code': self.bundle_code,
            'marble_thickness': self.marble_thickness,
        })

        if hasattr(self, 'pedimento_number') and self.pedimento_number:
            vals['pedimento_number'] = self.pedimento_number

        _logger.info(f"Move line creado con valores: {vals}")
        return vals

    def _create_move_lines(self):
        res = super()._create_move_lines()
        for move in self:
            for line in move.move_line_ids:
                if not line.lot_id and move.lot_id:
                    line.lot_id = move.lot_id
                for attr in ('marble_height', 'marble_width', 'marble_sqm',
                             'lot_general', 'bundle_code', 'marble_thickness'):
                    if not getattr(line, attr):
                        setattr(line, attr, getattr(move, attr))
                if hasattr(move, 'pedimento_number') and hasattr(line, 'pedimento_number'):
                    if not line.pedimento_number and move.pedimento_number:
                        line.pedimento_number = move.pedimento_number
        return res

    def _action_assign(self, force_qty=None):
        super()._action_assign(force_qty=force_qty)

        for move in self.filtered(lambda m: m.state in ('confirmed', 'partially_available', 'waiting')):
            if move.product_id.tracking != 'none' and move.so_lot_id:
                lot = move.so_lot_id
                _logger.info(f"Forzando reserva en lote {lot.name} para Move {move.id}")

                already_reserved = sum(move.move_line_ids.mapped('product_uom_qty'))
                missing_to_reserve = move.product_uom_qty - already_reserved

                if missing_to_reserve > 0:
                    available_qty = self.env['stock.quant']._get_available_quantity(
                        move.product_id, move.location_id, lot_id=lot,
                        package_id=False, owner_id=False, strict=True
                    )
                    if available_qty <= 0:
                        _logger.warning(f"No hay stock disponible en el lote {lot.name}.")
                        continue

                    qty_to_reserve = min(missing_to_reserve, available_qty)

                    existing_line = move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)
                    if existing_line:
                        existing_line.product_uom_qty += qty_to_reserve
                    else:
                        line_vals = {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            'product_uom_qty': qty_to_reserve,
                        }
                        if hasattr(move, 'pedimento_number') and move.pedimento_number:
                            line_vals['pedimento_number'] = move.pedimento_number
                        self.env['stock.move.line'].create(line_vals)
        return True
