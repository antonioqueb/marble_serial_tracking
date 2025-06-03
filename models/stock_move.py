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
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')

    # Campo computado para distinguir entregas
    is_outgoing = fields.Boolean(
        string='Es Salida',
        compute='_compute_is_outgoing',
        store=True
    )

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Calcula automáticamente los m² basado en altura x ancho
        """
        for move in self:
            move.marble_sqm = (move.marble_height or 0.0) * (move.marble_width or 0.0)
            _logger.debug(f"[MARBLE-COMPUTE] Stock Move ID {move.id}: altura={move.marble_height}, ancho={move.marble_width} → m²={move.marble_sqm}")

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        """
        OnChange para mostrar cambios inmediatos en la interfaz
        """
        for move in self:
            _logger.info(f"[MARBLE-ONCHANGE] Stock Move ID {move.id} → altura={move.marble_height}, ancho={move.marble_width}, lote={move.lot_general}")

    def write(self, vals):
        """
        Método write mejorado - Delega la creación de lotes a StockMoveLine
        """
        # Si no hay cambios relacionados con lotes, usar comportamiento normal
        if not any(field in vals for field in ['lot_general', 'marble_height', 'marble_width', 'marble_thickness']):
            return super().write(vals)

        _logger.info(f"[STOCK-MOVE-WRITE] Actualizando {len(self)} moves con campos de mármol")

        # Para moves de entrada con lot_general, propagar a las move_lines
        for move in self:
            if 'lot_general' in vals and vals['lot_general']:
                picking_code = move.picking_type_id.code
                if picking_code == 'incoming':
                    _logger.info(f"[STOCK-MOVE-WRITE] Propagando lot_general '{vals['lot_general']}' a move_lines del move {move.id}")
                    
                    # Propagar a move_lines que no tienen lote
                    move_lines_without_lot = move.move_line_ids.filtered(lambda ml: not ml.lot_id)
                    if move_lines_without_lot:
                        # Los move_lines se encargarán de crear los lotes con su método write() mejorado
                        move_lines_without_lot.write({
                            'lot_general': vals['lot_general'],
                            'marble_height': vals.get('marble_height', move.marble_height),
                            'marble_width': vals.get('marble_width', move.marble_width),
                            'marble_thickness': vals.get('marble_thickness', move.marble_thickness),
                        })

        # Llamar al método padre para actualizar los campos del move
        res = super().write(vals)
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
                             'lot_general', 'marble_thickness'):
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