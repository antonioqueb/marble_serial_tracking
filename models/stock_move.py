# models/stock_move.py

from odoo import models, fields, api
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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Agregar logs al crear stock moves
        """
        _logger.info("🆕 DEBUG: StockMove.create llamado con %s moves", len(vals_list))
        
        for i, vals in enumerate(vals_list):
            _logger.info("🆕 DEBUG: Move %s - Producto ID: %s, Nombre: %s", 
                        i, vals.get('product_id'), vals.get('name'))
            _logger.info("🆕 DEBUG: Move %s - Altura: %s, Ancho: %s, m²: %s, Lote: %s, PO Line: %s", 
                        i, vals.get('marble_height'), vals.get('marble_width'), 
                        vals.get('marble_sqm'), vals.get('lot_general'), vals.get('purchase_line_id'))
        
        moves = super().create(vals_list)
        
        _logger.info("🆕 DEBUG: Moves creados - Total: %s", len(moves))
        for move in moves:
            _logger.info("🆕 DEBUG: Move creado ID: %s - Producto: %s, Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.id, move.product_id.name, move.marble_height, move.marble_width, 
                        move.marble_sqm, move.lot_general)
        
        return moves

    def write(self, vals):
        """
        Agregar logs al escribir stock moves
        """
        if vals:
            _logger.info("✏️ DEBUG: StockMove.write llamado para %s moves", len(self))
            _logger.info("✏️ DEBUG: Valores a escribir: %s", vals)
            
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Antes: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
        # El write se centra en su funcionalidad principal.
        result = super().write(vals)
        
        if vals and any(key.startswith('marble_') or key == 'lot_general' for key in vals.keys()):
            for move in self:
                _logger.info("✏️ DEBUG: Move %s - Después: Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                           move.id, move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
        
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

    # ===== MÉTODOS PARA PREVENIR AGRUPACIÓN =====

    def _search_picking_for_assignation(self):
        """
        Sobrescribir para evitar que se agrupen moves con diferentes datos de mármol
        """
        result = super()._search_picking_for_assignation()
        return result

    def _key_assign_picking(self):
        """
        Sobrescribir la clave de agrupación para incluir datos de mármol
        """
        key = super()._key_assign_picking()
        # Añadir datos de mármol a la clave para evitar agrupación incorrecta
        marble_key = (
            self.marble_height or 0.0,
            self.marble_width or 0.0, 
            self.marble_sqm or 0.0,
            self.lot_general or '',
            self.marble_thickness or 0.0,
            self.numero_contenedor or '',
            self.purchase_line_id.id if self.purchase_line_id else 0,
        )
        
        final_key = key + marble_key
        _logger.info("🔑 DEBUG: _key_assign_picking para move %s - Clave: %s", self.id, final_key)
        return final_key

    @api.model 
    def _prepare_merge_moves_distinct_fields(self):
        """
        Especificar qué campos deben ser distintos para evitar merge
        """
        distinct_fields = super()._prepare_merge_moves_distinct_fields()
        # Añadir campos de mármol que deben mantenerse distintos
        marble_fields = [
            'marble_height', 'marble_width', 'marble_sqm', 
            'lot_general', 'marble_thickness', 'numero_contenedor',
            'purchase_line_id'
        ]
        distinct_fields.extend(marble_fields)
        return distinct_fields

    def _merge_moves_fields(self):
        """
        Sobrescribir para evitar que se fusionen moves con diferentes datos de mármol
        """
        result = super()._merge_moves_fields()
        # Añadir campos de mármol que no deben fusionarse
        marble_fields = {
            'marble_height', 'marble_width', 'marble_sqm',
            'lot_general', 'marble_thickness', 'numero_contenedor'
        }
        # Eliminar campos de mármol de los campos que se pueden fusionar
        for field in marble_fields:
            if field in result:
                result.pop(field)
        return result

    def _should_be_assigned(self):
        """
        Sobrescribir para considerar los datos de mármol en la asignación
        """
        result = super()._should_be_assigned()
        # Si tiene datos de mármol específicos, debe ser asignado individualmente
        if self.marble_sqm > 0 or self.lot_general:
            return True
        return result

    def _merge_moves(self, merge_into=False):
        """
        Prevenir merge de moves con diferentes características de mármol
        """
        _logger.info("🔄 DEBUG: _merge_moves llamado para %s moves", len(self))
        
        # Agrupar moves por sus características de mármol
        marble_groups = {}
        for move in self:
            marble_key = (
                move.marble_height or 0.0,
                move.marble_width or 0.0,
                move.marble_sqm or 0.0,
                move.lot_general or '',
                move.marble_thickness or 0.0,
                move.numero_contenedor or '',
                move.purchase_line_id.id if move.purchase_line_id else 0,
            )
            if marble_key not in marble_groups:
                marble_groups[marble_key] = self.env['stock.move']
            marble_groups[marble_key] |= move
            
            _logger.info("🔄 DEBUG: Move %s agrupado con clave: %s", move.id, marble_key)

        _logger.info("🔄 DEBUG: Grupos de mármol creados: %s", len(marble_groups))

        # Solo hacer merge dentro de cada grupo con las mismas características
        merged_moves = self.env['stock.move']
        for i, (marble_key, group_moves) in enumerate(marble_groups.items()):
            _logger.info("🔄 DEBUG: Procesando grupo %s con %s moves", i, len(group_moves))
            
            if len(group_moves) > 1:
                _logger.info("🔄 DEBUG: Haciendo merge de grupo %s", i)
                merged_moves |= super(StockMove, group_moves)._merge_moves(merge_into)
            else:
                _logger.info("🔄 DEBUG: Grupo %s no necesita merge", i)
                merged_moves |= group_moves

        _logger.info("🔄 DEBUG: Moves después del merge: %s", len(merged_moves))
        return merged_moves