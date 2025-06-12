from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_level = fields.Selection(
        [
            ('max', 'Precio Máximo'),
            ('avg', 'Precio Promedio'),
            ('min', 'Precio Mínimo'),
            ('manual', 'Manual')
        ],
        string='Nivel de Precio',
        default='max'
    )
    applied_price_per_sqm = fields.Float(
        string='Precio por m² Aplicado',
        digits='Product Price',
        readonly=False
    )

    @api.onchange('lot_id', 'price_level')
    def _onchange_lot_pricing(self):
        """
        Ajusta applied_price_per_sqm y price_unit según el lote y nivel seleccionado,
        salvo en modo manual.
        """
        for line in self:
            if line.lot_id and line.product_id and line.price_level != 'manual':
                if line.price_level == 'max':
                    price_per_sqm = line.product_id.price_per_sqm_max
                elif line.price_level == 'avg':
                    price_per_sqm = line.product_id.price_per_sqm_avg
                else:
                    price_per_sqm = line.product_id.price_per_sqm_min

                line.applied_price_per_sqm = price_per_sqm or 0.0

                if price_per_sqm and line.marble_sqm:
                    line.price_unit = line.marble_sqm * price_per_sqm
            elif line.price_level == 'manual':
                # En modo manual, el usuario define applied_price_per_sqm
                pass
            else:
                line.applied_price_per_sqm = 0.0

    @api.onchange('applied_price_per_sqm', 'marble_sqm')
    def _onchange_manual_pricing(self):
        """
        Recalcula price_unit si se modifica manualmente applied_price_per_sqm o marble_sqm.
        """
        for line in self:
            if line.applied_price_per_sqm and line.marble_sqm:
                line.price_unit = line.marble_sqm * line.applied_price_per_sqm

    @api.onchange('price_level')
    def _onchange_price_level_mode(self):
        """
        Muestra advertencia al activar modo manual.
        """
        if self.price_level == 'manual':
            return {
                'warning': {
                    'title': 'Modo Manual Activado',
                    'message': (
                        'Ahora puedes editar directamente el precio por m². '
                        'El precio unitario se calculará automáticamente.'
                    )
                }
            }
