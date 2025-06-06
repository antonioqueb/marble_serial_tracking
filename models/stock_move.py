# models/stock_move.py
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    # Campos existentes
    so_lot_id = fields.Many2one('stock.lot', string="Lote Forzado (Venta)")
    lot_id = fields.Many2one('stock.lot', string='Número de Serie (Venta)')
    marble_height = fields.Float('Altura (m)')
    marble_width = fields.Float('Ancho (m)')
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote')
    marble_thickness = fields.Float('Grosor (cm)')
    is_outgoing = fields.Boolean(string='Es Salida', compute='_compute_is_outgoing', store=True)

    # ========== NUEVOS CAMPOS PARA WIDGET DUAL ==========
    lot_selection_mode = fields.Selection([
        ('existing', 'Seleccionar Lote Existente'),
        ('manual', 'Crear Nuevo Lote')
    ], string='Modo de Lote', default='manual')
    
    existing_lot_id = fields.Many2one(
        'stock.lot', 
        string='Lote Existente',
        domain="[('product_id', '=', product_id), ('id', 'in', available_lot_ids)]"
    )
    
    available_lot_ids = fields.Many2many(
        'stock.lot', 
        compute='_compute_available_lots',
        string='Lotes Disponibles'
    )

    @api.depends('product_id')
    def _compute_available_lots(self):
        """Calcular lotes disponibles con stock para el producto"""
        for move in self:
            if move.product_id:
                # Buscar quants con stock disponible
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                    ('lot_id', '!=', False)
                ])
                move.available_lot_ids = quants.mapped('lot_id')
            else:
                move.available_lot_ids = False

    @api.onchange('lot_selection_mode')
    def _onchange_lot_selection_mode(self):
        """Reset campos cuando cambia el modo"""
        if self.lot_selection_mode == 'existing':
            # Limpiar campos manuales
            self.lot_general = ''
            self.marble_height = 0.0
            self.marble_width = 0.0
            self.marble_thickness = 0.0
        else:  # manual
            # Limpiar selección existente
            self.existing_lot_id = False

    @api.onchange('existing_lot_id')
    def _onchange_existing_lot_id(self):
        """Rellenar datos automáticamente cuando se selecciona un lote existente"""
        if self.existing_lot_id and self.lot_selection_mode == 'existing':
            lot = self.existing_lot_id
            self.lot_general = lot.lot_general
            self.marble_height = lot.marble_height
            self.marble_width = lot.marble_width
            self.marble_sqm = lot.marble_sqm
            self.marble_thickness = lot.marble_thickness
            
            # Para salidas, también asignar el lot_id
            if self.is_outgoing:
                self.lot_id = lot.id
                self.so_lot_id = lot.id
            
            _logger.info(f"[LOT-SELECT] Move {self.id}: Datos cargados desde lote {lot.name}")

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
        """Método write mejorado para manejar ambos modos"""
        # Si no hay cambios relacionados con lotes, usar comportamiento normal
        if not any(field in vals for field in ['lot_general', 'marble_height', 'marble_width', 'marble_thickness', 'existing_lot_id']):
            return super().write(vals)

        _logger.info(f"[STOCK-MOVE-WRITE] Actualizando {len(self)} moves con campos de mármol")

        for move in self:
            # Determinar si estamos en modo existente o manual
            if 'existing_lot_id' in vals and vals['existing_lot_id']:
                # Modo existente: usar datos del lote seleccionado
                lot = self.env['stock.lot'].browse(vals['existing_lot_id'])
                if lot:
                    vals.update({
                        'lot_general': lot.lot_general,
                        'marble_height': lot.marble_height,
                        'marble_width': lot.marble_width,
                        'marble_sqm': lot.marble_sqm,
                        'marble_thickness': lot.marble_thickness,
                    })
                    
                    # Para salidas, asignar lot_id
                    if move.is_outgoing:
                        vals['lot_id'] = lot.id
                        vals['so_lot_id'] = lot.id
                    
                    _logger.info(f"[STOCK-MOVE-WRITE] Modo existente: usando lote {lot.name}")
            
            elif 'lot_general' in vals and vals['lot_general'] and not move.is_outgoing:
                # Modo manual para ingresos: crear nuevo lote (comportamiento actual)
                move_lines_without_lot = move.move_line_ids.filtered(lambda ml: not ml.lot_id)
                if move_lines_without_lot:
                    move_lines_without_lot.write({
                        'lot_general': vals['lot_general'],
                        'marble_height': vals.get('marble_height', move.marble_height),
                        'marble_width': vals.get('marble_width', move.marble_width),
                        'marble_thickness': vals.get('marble_thickness', move.marble_thickness),
                    })

        # Llamar al método padre para actualizar los campos del move
        result = super().write(vals)
        
        # CRÍTICO: Propagar datos a move_lines existentes después del write
        self._propagate_marble_data_to_move_lines()
        
        return result

    def _propagate_marble_data_to_move_lines(self):
        """
        Propagar datos de mármol del move a sus move_lines
        """
        for move in self:
            if move.move_line_ids:
                move_line_vals = {
                    'marble_height': move.marble_height,
                    'marble_width': move.marble_width,
                    'marble_sqm': move.marble_sqm,
                    'lot_general': move.lot_general,
                    'marble_thickness': move.marble_thickness,
                }
                
                # Si hay lot_id en el move, también propagarlo
                if move.lot_id:
                    move_line_vals['lot_id'] = move.lot_id.id
                
                # Actualizar todas las move_lines
                move.move_line_ids.write(move_line_vals)
                _logger.info(f"[PROPAGATE] Move {move.id}: Datos propagados a {len(move.move_line_ids)} move_lines")

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super()._prepare_move_line_vals(quantity, reserved_quant)

        # MEJORADO: Asegurar que todos los datos se incluyan
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
        })

        # Lot ID para salidas
        if self.lot_id:
            vals['lot_id'] = self.lot_id.id

        # Pedimento si existe
        if hasattr(self, 'pedimento_number') and self.pedimento_number:
            vals['pedimento_number'] = self.pedimento_number

        _logger.info(f"[PREPARE-MOVE-LINE] Move {self.id}: {vals}")
        return vals

    def _create_move_lines(self):
        """Sobrescribir para asegurar propagación correcta"""
        res = super()._create_move_lines()
        
        # Después de crear, propagar datos
        for move in self:
            if move.move_line_ids:
                move._propagate_marble_data_to_move_lines()
        
        return res

    def _action_assign(self):
        """Sobrescribir para manejar asignación con lotes específicos"""
        result = super()._action_assign()
        
        # Después de asignar, asegurar que los datos estén propagados
        for move in self:
            if move.lot_id and move.move_line_ids:
                # Forzar lot_id en todas las move_lines
                for line in move.move_line_ids:
                    if not line.lot_id:
                        line.lot_id = move.lot_id
                
                # Propagar datos de mármol
                move._propagate_marble_data_to_move_lines()
        
        return result

    def _action_done(self, cancel_backorder=False):
        """CORREGIDO: Aceptar parámetro cancel_backorder"""
        # Propagar datos antes de finalizar
        for move in self:
            if move.move_line_ids:
                move._propagate_marble_data_to_move_lines()
        
        return super()._action_done(cancel_backorder=cancel_backorder)