# models/stock_move.py

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class StockMove(models.Model):
    _inherit = 'stock.move'

    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    is_outgoing = fields.Boolean(string='Es Salida', compute='_compute_is_outgoing', store=True)
    pedimento_number = fields.Char(string='Número de Pedimento', size=18)
    numero_contenedor = fields.Char('Número de Contenedor')

    lot_selection_mode = fields.Selection([
        ('existing', 'Seleccionar Lote Existente'),
        ('manual', 'Crear Nuevo Lote')
    ], string='Modo de Lote', default='manual')
    existing_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote Existente',
        domain="[('product_id','=',product_id),('id','in',available_lot_ids)]"
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_lots',
        string='Lotes Disponibles'
    )

    @api.depends('product_id')
    def _compute_available_lots(self):
        for move in self:
            if move.product_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '!=', False),
                ])
                move.available_lot_ids = quants.mapped('lot_id')
            else:
                move.available_lot_ids = False

    @api.onchange('lot_selection_mode')
    def _onchange_lot_selection_mode(self):
        if self.lot_selection_mode == 'existing':
            self.lot_general = False
            self.marble_height = 0.0
            self.marble_width = 0.0
            self.marble_thickness = 0.0
            self.pedimento_number = False
        else:
            self.existing_lot_id = False

    @api.onchange('existing_lot_id')
    def _onchange_existing_lot_id(self):
        """
        Al seleccionar un lote existente, este onchange hace dos cosas:
        1. Actualiza los datos de la línea actual.
        2. Ajusta otras líneas del mismo albarán si están desincronizadas.
        """
        if self.lot_selection_mode == 'existing' and self.existing_lot_id:
            lot = self.existing_lot_id

            # 1. Actualiza la línea actual
            self.lot_general = lot.lot_general
            self.marble_height = lot.marble_height
            self.marble_width = lot.marble_width
            self.marble_sqm = lot.marble_sqm
            self.marble_thickness = lot.marble_thickness
            self.lot_id = lot.id
            self.so_lot_id = lot.id
            self.numero_contenedor = lot.numero_contenedor

            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            self.pedimento_number = quant.pedimento_number or ''

            # 2. Sincroniza otras líneas del mismo picking
            if self.picking_id:
                for other_move in self.picking_id.move_ids_without_package:
                    if other_move == self._origin:
                        continue
                    if other_move.lot_id and other_move.marble_sqm != other_move.lot_id.marble_sqm:
                        other_quant = self.env['stock.quant'].search([
                            ('lot_id', '=', other_move.lot_id.id),
                            ('quantity', '>', 0),
                            ('location_id.usage', '=', 'internal'),
                        ], limit=1, order='in_date DESC')
                        other_move.lot_general = other_move.lot_id.lot_general
                        other_move.marble_height = other_move.lot_id.marble_height
                        other_move.marble_width = other_move.lot_id.marble_width
                        other_move.marble_sqm = other_move.lot_id.marble_sqm
                        other_move.marble_thickness = other_move.lot_id.marble_thickness
                        other_move.pedimento_number = other_quant.pedimento_number or ''

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for move in self:
            move.marble_sqm = (move.marble_height or 0.0) * (move.marble_width or 0.0)

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = (move.picking_type_id.code == 'outgoing')

    def write(self, vals):
        # El write se centra en su funcionalidad principal.
        result = super().write(vals)
        if self:
            self._propagate_marble_data_to_move_lines()
        return result

    def _propagate_marble_data_to_move_lines(self):
        """
        Propaga los datos de mármol y lote a las líneas de movimiento asociadas.
        """
        for move in self:
            if not move.exists():
                continue
            if move.move_line_ids:
                data = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                    'pedimento_number': move.pedimento_number or '',
                    'numero_contenedor': move.numero_contenedor,
                }
                if move.lot_id:
                    data['lot_id'] = move.lot_id.id
                move.move_line_ids.write(data)

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        marble_data = {
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'pedimento_number': self.pedimento_number or '',
            'numero_contenedor': self.numero_contenedor or '',
        }
        if self.is_outgoing and self.lot_id:
            marble_data['lot_id'] = self.lot_id.id
        vals.update(marble_data)
        return vals

    def _action_assign(self):
        result = super()._action_assign()
        for move in self:
            if move.move_line_ids and (move.lot_id or move.marble_sqm or move.lot_general):
                move._propagate_marble_data_to_move_lines()
        return result

    def _action_done(self, cancel_backorder=False):
        for move in self:
            move._propagate_marble_data_to_move_lines()
        return super()._action_done(cancel_backorder=cancel_backorder)
