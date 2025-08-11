# models/purchase_order_line.py

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    marble_height = fields.Float('Altura (m)', store=True)
    marble_width = fields.Float('Ancho (m)', store=True)
    marble_sqm = fields.Float('m²', compute='_compute_marble_sqm', store=True, readonly=False)
    lot_general = fields.Char('Lote', store=True)
    marble_thickness = fields.Float('Grosor (cm)')
    numero_contenedor = fields.Char('Número de Contenedor', store=True)

    @api.depends('marble_height', 'marble_width')
    def _compute_marble_sqm(self):
        """
        Lógica de cálculo HÍBRIDA:
        - Si se especifican altura y ancho, calcula los m².
        - Si NO se especifican, NO HACE NADA, permitiendo que el valor
          introducido manualmente por el usuario se conserve.
        """
        for line in self:
            if line.marble_height > 0 and line.marble_width > 0:
                line.marble_sqm = line.marble_height * line.marble_width

    @api.onchange('marble_height', 'marble_width', 'lot_general')
    def _onchange_marble_fields(self):
        return

    def write(self, vals):
        res = super().write(vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        return lines

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        
        _logger.info("🔍 DEBUG: _prepare_stock_move_vals para línea PO %s", self.id)
        _logger.info("🔍 DEBUG: Producto: %s, Cantidad: %s", self.product_id.name, product_uom_qty)
        _logger.info("🔍 DEBUG: Datos mármol - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                    self.marble_height, self.marble_width, self.marble_sqm, self.lot_general)
        
        # CLAVE: Añadir un identificador único para evitar agrupación
        vals.update({
            'marble_height': self.marble_height or 0.0,
            'marble_width': self.marble_width or 0.0,
            'marble_sqm': self.marble_sqm or 0.0,
            'lot_general': self.lot_general or '',
            'marble_thickness': self.marble_thickness or 0.0,
            'numero_contenedor': self.numero_contenedor or '',
            # Añadir referencia única a la línea de compra para evitar agrupación
            'purchase_line_id': self.id,
            'origin': f"{self.order_id.name} - Línea {self.id}",
        })
        
        _logger.info("🔍 DEBUG: Stock move vals preparados: %s", vals)
        return vals

    def _create_stock_moves(self, picking):
        """
        Sobrescribir para asegurar que cada línea genera su propio move independiente
        """
        _logger.info("🚀 DEBUG: _create_stock_moves llamado para %s líneas", len(self))
        
        moves = self.env['stock.move']
        
        for line in self:
            _logger.info("🔄 DEBUG: Procesando línea PO %s - Producto: %s", line.id, line.product_id.name)
            _logger.info("🔄 DEBUG: Datos línea - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        line.marble_height, line.marble_width, line.marble_sqm, line.lot_general)
            
            # Crear un move individual para cada línea
            move_vals = line._prepare_stock_move_vals(
                picking, 
                line.price_unit, 
                line.product_qty, 
                line.product_uom
            )
            
            # Asegurar que el move tenga un nombre único
            move_vals['name'] = f"{line.order_id.name} - {line.product_id.name} - Línea {line.id}"
            
            _logger.info("🔄 DEBUG: Creando move con vals: %s", move_vals)
            
            move = self.env['stock.move'].create(move_vals)
            moves |= move
            
            _logger.info("✅ DEBUG: Move creado ID: %s - Nombre: %s", move.id, move.name)
            _logger.info("✅ DEBUG: Move datos - Altura: %s, Ancho: %s, m²: %s, Lote: %s", 
                        move.marble_height, move.marble_width, move.marble_sqm, move.lot_general)
            
        _logger.info("🏁 DEBUG: Total moves creados: %s", len(moves))
        return moves

    def _get_stock_move_map(self):
        """
        Sobrescribir para evitar que Odoo agrupe movimientos por producto
        """
        _logger.info("🗺️ DEBUG: _get_stock_move_map llamado para %s líneas", len(self))
        
        # En lugar de agrupar por producto, crear un mapeo único por línea
        move_map = {}
        for line in self:
            # Usar el ID de la línea como clave única
            key = f"line_{line.id}_{line.product_id.id}"
            move_map[key] = {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'lines': [line],
            }
            _logger.info("🗺️ DEBUG: Mapeando línea %s con clave única: %s", line.id, key)
        
        _logger.info("🗺️ DEBUG: Move map final: %s", move_map)
        return move_map