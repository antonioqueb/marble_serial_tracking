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
        ('min', 'Precio Mínimo')
    ], string='Nivel de Precio', default='max')

    # Campo para mostrar el precio por m² aplicado
    applied_price_per_sqm = fields.Float(
        string='Precio por m² Aplicado',
        digits='Product Price',
        readonly=True
    )

    @api.onchange('lot_id', 'price_level')
    def _onchange_lot_pricing(self):
        """
        Calcula automáticamente el precio unitario basado en:
        - m² del lote seleccionado
        - Nivel de precio elegido del producto
        Solo aplica cuando hay un lote seleccionado
        """
        for line in self:
            if line.lot_id and line.product_id:
                # Obtener precio por m² según el nivel seleccionado
                if line.price_level == 'max':
                    price_per_sqm = line.product_id.price_per_sqm_max
                elif line.price_level == 'avg':
                    price_per_sqm = line.product_id.price_per_sqm_avg
                else:  # min
                    price_per_sqm = line.product_id.price_per_sqm_min

                # Calcular precio unitario: m² × precio_por_m²
                if price_per_sqm and line.marble_sqm:
                    line.price_unit = line.marble_sqm * price_per_sqm
                    line.applied_price_per_sqm = price_per_sqm
                    
                    _logger.info(
                        f"[PRECIO-AUTO] SO Line {line.id}: "
                        f"m²={line.marble_sqm}, precio_por_m²={price_per_sqm}, "
                        f"precio_unitario={line.price_unit}"
                    )
                else:
                    line.applied_price_per_sqm = 0.0
                    _logger.warning(
                        f"[PRECIO-AUTO] SO Line {line.id}: "
                        f"Sin precio configurado para nivel '{line.price_level}'"
                    )
            else:
                # Si no hay lote, el usuario debe ingresar el precio manualmente
                line.applied_price_per_sqm = 0.0