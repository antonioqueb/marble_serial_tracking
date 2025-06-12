# models/stock_move.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

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
        if self.lot_selection_mode == 'existing' and self.existing_lot_id:
            lot = self.existing_lot_id
            self.lot_general = lot.lot_general
            self.marble_height = lot.marble_height
            self.marble_width = lot.marble_width
            self.marble_sqm = lot.marble_sqm
            self.marble_thickness = lot.marble_thickness

            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], limit=1, order='in_date DESC')
            self.pedimento_number = quant.pedimento_number or False

            if self.is_outgoing:
                self.lot_id = lot.id
                self.so_lot_id = lot.id

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        for move in self:
            move.marble_sqm = (move.marble_height or 0.0) * (move.marble_width or 0.0)

    @api.depends('picking_type_id.code')
    def _compute_is_outgoing(self):
        for move in self:
            move.is_outgoing = move.picking_type_id.code == 'outgoing'

    def write(self, vals):
        _logger.info(f"[STOCK-MOVE-WRITE] === INICIO write para {len(self)} moves ===")
        _logger.info(f"[STOCK-MOVE-WRITE] Valores a escribir: {vals}")
        
        # Handle existing-lot mode
        if vals.get('existing_lot_id'):
            lot = self.env['stock.lot'].browse(vals['existing_lot_id'])
            if lot:
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ], limit=1, order='in_date DESC')
                vals.update({
                    'lot_general': lot.lot_general,
                    'marble_height': lot.marble_height,
                    'marble_width': lot.marble_width,
                    'marble_sqm': lot.marble_sqm,
                    'marble_thickness': lot.marble_thickness,
                    'pedimento_number': quant.pedimento_number or False,
                })
                if self.is_outgoing:
                    vals['lot_id'] = lot.id
                    vals['so_lot_id'] = lot.id

        # Handle manual-lot creation on incoming
        if vals.get('lot_general') and not self.is_outgoing:
            lines = self.move_line_ids.filtered(lambda ml: not ml.lot_id)
            if lines:
                lines.write({
                    'lot_general': vals['lot_general'],
                    'marble_height': vals.get('marble_height', self.marble_height),
                    'marble_width': vals.get('marble_width', self.marble_width),
                    'marble_thickness': vals.get('marble_thickness', self.marble_thickness),
                    'pedimento_number': vals.get('pedimento_number', self.pedimento_number),
                })

        result = super().write(vals)
        
        _logger.info(f"[STOCK-MOVE-WRITE] Llamando _propagate_marble_data_to_move_lines")
        self._propagate_marble_data_to_move_lines()
        
        _logger.info(f"[STOCK-MOVE-WRITE] === FIN write ===")
        return result

    def _propagate_marble_data_to_move_lines(self):
        """
        Propagar datos de mármol del move a sus move_lines
        """
        _logger.info(f"[PROPAGATE-DATA] === INICIO propagación para {len(self)} moves ===")
        
        for move in self:
            _logger.info(f"[PROPAGATE-DATA] Move {move.id} - {move.product_id.name}")
            _logger.info(f"[PROPAGATE-DATA] Datos actuales del move:")
            _logger.info(f"  - marble_height: {move.marble_height}")
            _logger.info(f"  - marble_width: {move.marble_width}")
            _logger.info(f"  - marble_sqm: {move.marble_sqm}")
            _logger.info(f"  - lot_general: {move.lot_general}")
            _logger.info(f"  - pedimento_number: {move.pedimento_number}")
            _logger.info(f"  - lot_id: {move.lot_id.id if move.lot_id else 'None'}")
            
            if move.move_line_ids:
                _logger.info(f"[PROPAGATE-DATA] Propagando a {len(move.move_line_ids)} move_lines")
                
                data = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                    'pedimento_number': move.pedimento_number or '',
                }
                if move.lot_id:
                    data['lot_id'] = move.lot_id.id
                    
                move.move_line_ids.write(data)
                
                # Verificar propagación
                for line in move.move_line_ids:
                    _logger.info(f"[PROPAGATE-DATA] Move line {line.id} después de propagación:")
                    _logger.info(f"  - marble_height: {line.marble_height}")
                    _logger.info(f"  - marble_width: {line.marble_width}")
                    _logger.info(f"  - marble_sqm: {line.marble_sqm}")
                    _logger.info(f"  - lot_general: {line.lot_general}")
                    _logger.info(f"  - lot_id: {line.lot_id.id if line.lot_id else 'None'}")
            else:
                _logger.info(f"[PROPAGATE-DATA] Move {move.id} no tiene move_lines")
                
        _logger.info(f"[PROPAGATE-DATA] === FIN propagación ===")

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        _logger.info(f"[PREPARE-MOVE-LINE] === INICIO para move {self.id} ===")
        
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)
        
        marble_data = {
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'pedimento_number': self.pedimento_number or '',
        }
        
        if self.is_outgoing and self.lot_id:
            marble_data['lot_id'] = self.lot_id.id
            _logger.info(f"[PREPARE-MOVE-LINE] Es salida, asignando lot_id: {self.lot_id.id}")
            
        vals.update(marble_data)
        
        _logger.info(f"[PREPARE-MOVE-LINE] Valores finales para move_line:")
        _logger.info(f"  - marble_height: {vals.get('marble_height')}")
        _logger.info(f"  - marble_width: {vals.get('marble_width')}")
        _logger.info(f"  - marble_sqm: {vals.get('marble_sqm')}")
        _logger.info(f"  - lot_general: {vals.get('lot_general')}")
        _logger.info(f"  - lot_id: {vals.get('lot_id')}")
        _logger.info(f"[PREPARE-MOVE-LINE] === FIN ===")
        
        return vals

    def _create_move_lines(self):
        _logger.info(f"[CREATE-MOVE-LINES] Creando move_lines para {len(self)} moves")
        res = super()._create_move_lines()
        
        for move in self:
            _logger.info(f"[CREATE-MOVE-LINES] Propagando datos para move {move.id}")
            move._propagate_marble_data_to_move_lines()
            
        return res

    def _action_assign(self):
        _logger.info(f"[ACTION-ASSIGN] === INICIO para {len(self)} moves ===")
        result = super()._action_assign()
        
        for move in self:
            if move.move_line_ids and (move.marble_sqm or move.lot_general):
                _logger.info(f"[ACTION-ASSIGN] Move {move.id} tiene datos de mármol, propagando...")
                
                data = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                    'pedimento_number': move.pedimento_number,
                }
                if move.lot_id:
                    data['lot_id'] = move.lot_id.id
                    
                _logger.info(f"[ACTION-ASSIGN] Datos a propagar: {data}")
                move.move_line_ids.write(data)
                
                # Verificar
                for line in move.move_line_ids:
                    _logger.info(f"[ACTION-ASSIGN] Move line {line.id} actualizada:")
                    _logger.info(f"  - marble_sqm: {line.marble_sqm}")
                    _logger.info(f"  - lot_id: {line.lot_id.id if line.lot_id else 'None'}")
                    
        _logger.info(f"[ACTION-ASSIGN] === FIN ===")
        return result

    def _action_done(self, cancel_backorder=False):
        _logger.info(f"[ACTION-DONE] Finalizando {len(self)} moves")
        
        for move in self:
            _logger.info(f"[ACTION-DONE] Propagando datos finales para move {move.id}")
            move._propagate_marble_data_to_move_lines()
            
        return super()._action_done(cancel_backorder=cancel_backorder)