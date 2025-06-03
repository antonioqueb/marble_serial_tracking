# models/sale_order_line_pricing.py
# Is functional and should be placed in the models directory of your Odoo module.
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Campo para seleccionar el nivel de precio
    price_level = fields.Selection([
        ('max', 'Precio Máximo'),
        ('avg', 'Precio Promedio'),
        ('min', 'Precio Mínimo'),
        ('manual', 'Manual')  # NUEVA OPCIÓN AGREGADA
    ], string='Nivel de Precio', default='max')

    # Campo para mostrar/editar el precio por m² aplicado
    applied_price_per_sqm = fields.Float(
        string='Precio por m² Aplicado',
        digits='Product Price',
        readonly=False  # CAMBIADO: Ahora es editable
    )

    @api.onchange('lot_id', 'price_level')
    def _onchange_lot_pricing(self):
        """
        Calcula automáticamente el precio unitario basado en:
        - m² del lote seleccionado
        - Nivel de precio elegido del producto
        Solo aplica cuando hay un lote seleccionado y no es modo manual
        """
        for line in self:
            if line.lot_id and line.product_id and line.price_level != 'manual':
                # Obtener precio por m² según el nivel seleccionado
                if line.price_level == 'max':
                    price_per_sqm = line.product_id.price_per_sqm_max
                elif line.price_level == 'avg':
                    price_per_sqm = line.product_id.price_per_sqm_avg
                else:  # min
                    price_per_sqm = line.product_id.price_per_sqm_min

                # Actualizar el campo applied_price_per_sqm
                line.applied_price_per_sqm = price_per_sqm

                # Calcular precio unitario: m² × precio_por_m²
                if price_per_sqm and line.marble_sqm:
                    line.price_unit = line.marble_sqm * price_per_sqm
                    
                    _logger.info(
                        f"[PRECIO-AUTO] SO Line {line.id}: "
                        f"m²={line.marble_sqm}, precio_por_m²={price_per_sqm}, "
                        f"precio_unitario={line.price_unit}"
                    )
                else:
                    _logger.warning(
                        f"[PRECIO-AUTO] SO Line {line.id}: "
                        f"Sin precio configurado para nivel '{line.price_level}'"
                    )
            elif line.price_level == 'manual':
                # En modo manual, el usuario debe especificar applied_price_per_sqm
                # No modificamos automáticamente el campo
                _logger.info(
                    f"[PRECIO-MANUAL] SO Line {line.id}: "
                    f"Modo manual activado - usuario debe especificar precio por m²"
                )
            else:
                # Si no hay lote, resetear
                line.applied_price_per_sqm = 0.0

    @api.onchange('applied_price_per_sqm', 'marble_sqm')
    def _onchange_manual_pricing(self):
        """
        Nuevo método: Recalcula el precio unitario cuando se edita manualmente 
        el precio por m² o los m²
        """
        for line in self:
            if line.applied_price_per_sqm and line.marble_sqm:
                # Calcular precio unitario basado en el precio por m² manual
                line.price_unit = line.marble_sqm * line.applied_price_per_sqm
                
                _logger.info(
                    f"[PRECIO-MANUAL] SO Line {line.id}: "
                    f"m²={line.marble_sqm}, precio_por_m²_manual={line.applied_price_per_sqm}, "
                    f"precio_unitario_calculado={line.price_unit}"
                )

    @api.onchange('price_level')
    def _onchange_price_level_mode(self):
        """
        Nuevo método: Cuando se cambia a modo manual, mostrar mensaje informativo
        """
        if self.price_level == 'manual':
            return {
                'warning': {
                    'title': 'Modo Manual Activado',
                    'message': 'Ahora puedes editar directamente el precio por m². '
                              'El precio unitario se calculará automáticamente.'
                }
            }