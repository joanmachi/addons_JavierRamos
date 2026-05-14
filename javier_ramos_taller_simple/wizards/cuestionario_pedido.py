import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
import math
_logger = logging.getLogger(__name__)

class Cuestionario(models.TransientModel):
    _name = 'javier_ramos_taller_simple.cuestionario'
    _inherit = ['multi.step.wizard.mixin']
    mostrar_boton = fields.Boolean(
 
        compute="_compute_mostrar_boton",
    )
    
    sale_order = fields.Many2one(
        comodel_name='sale.order',
        string="Pedido",
    )
    sale_order_line = fields.Many2one(
        comodel_name='sale.order.line',
        string="Linea pedido",
    )

    tipo_producto = fields.Selection(
        selection= [('unitario', 'Unitario'),('serie', 'Serie'),('conjunto', 'Conjunto')]
    )

    largo = fields.Float(string="Largo(L) mm")
    ancho = fields.Float(string="Ancho(A) mm")
    altura = fields.Float(string="Altura(H) mm")
    diametro = fields.Float(string="Diámetro(D) mm")

    componentes = fields.One2many(
        comodel_name="javier_ramos_taller_simple.componentes_aux",
        inverse_name="cuestionario_aux",
        string="Materia prima",
    )
    servicios = fields.One2many(
        comodel_name="javier_ramos_taller_simple.servicios_aux",
        inverse_name="cuestionario_aux",
        string="Servicios subcontratados",
    )
    componentes_conjunto = fields.One2many(
        comodel_name="javier_ramos_taller_simple.componentes_unitario_aux",
        inverse_name="cuestionario_aux",
        string="Productos",
    )
    servicios_conjunto = fields.One2many(
        comodel_name="javier_ramos_taller_simple.servicios_conjunto_aux",
        inverse_name="cuestionario_aux",
        string="Servicios subcontratados",
    )
    fases = fields.One2many(
        comodel_name="javier_ramos_taller_simple.fases_aux",
        inverse_name="cuestionario_aux",
        string="Operaciones",
    )

    size_producto = fields.Selection([
        ('pequeño', 'PEQUEÑO 100x100x100 mm'),
        ('mediano', 'MEDIANO 300x300x300 mm'),
        ('grande', 'GRANDE 500x900x200 mm'),
        ('muy_grande', 'MUY GRANDE 1000x1200x5-200 mm')
    ], string="Tamaño")

    @api.depends("state", "sale_order", "sale_order_line", "tipo_producto","componentes","fases", "servicios", "largo", "ancho", "altura", "diametro")
    def _compute_mostrar_boton(self):
        if self.tipo_producto == 'unitario' or self.tipo_producto == 'serie':
            if self.state == 'start' and not self.tipo_producto:
                self.mostrar_boton = False
            elif self.state == 'tres' and (self.largo == 0 and self.ancho == 0 and self.altura == 0 and self.diametro == 0):
    
                self.mostrar_boton = False
            elif self.state == 'tres' and self.diametro > 0 and self.largo == 0:
                self.mostrar_boton = False
            elif self.state == 'tres' and self.ancho > 0 and (self.largo == 0 or self.altura == 0):
                self.mostrar_boton = False
            elif self.state == 'tres' and self.altura > 0 and (self.largo == 0 or self.ancho == 0):
                self.mostrar_boton = False
            elif self.state == 'tres' and self.largo > 0 and (self.ancho == 0 or self.altura == 0) and self.diametro == 0:
                self.mostrar_boton = False
            elif self.state == 'final':
                self.mostrar_boton = False
            else:
                self.mostrar_boton = True
        if self.tipo_producto == 'conjunto':
            if self.state == 'start' and not self.tipo_producto:
                self.mostrar_boton = False
            elif self.state == 'final':
                self.mostrar_boton = False
            else:
                self.mostrar_boton = True
        if not self.tipo_producto:
            self.mostrar_boton = False

    @api.model
    def _selection_state(self):
        return [

            ('start', 'Tipo de producto'),
            ('dos', 'Componentes'),
            ('dos_conjunto', 'Componentes'),
            ('tres', 'Medidas'),
            ('cuatro', 'Servicios'),
            ('tres_conjunto', 'Servicios'),
            ('final', 'Fases'),
        ]
    
    def open_next(self):
        _logger.info('---- open_next ----')
        _logger.info(self.state)

        state_method = getattr(self, f"state_exit_{self.state}", None)
        if state_method is None:
            raise NotImplementedError(f"No method defined for state {self.state}")
        state_method()
        return self._reopen_self()



    def state_exit_start(self):
        if self.tipo_producto == 'conjunto':
            self.state = 'dos_conjunto'
        else:
            self.state = 'dos'
    def state_previous_dos_conjunto(self):
        self.state = 'start'
    def state_exit_dos_conjunto(self):
        self.state = 'tres_conjunto'
    def state_exit_dos(self):
        self.state = 'tres'
    def state_previous_tres_conjunto(self):
        self.state = 'dos_conjunto'
    def state_exit_tres_conjunto(self):
        self.state = 'final'
    def state_exit_tres(self):
        if self.largo and self.ancho and self.altura and self.diametro:
            raise UserError('No puedes rellenar todos los valores. Rellena largo, ancho y altura o largo y diametro')
        self.state = 'cuatro'
    def state_exit_cuatro(self):
        self.state = 'final'

    id_modelo = fields.Char(
 
        compute="_compute_id_model",
    )
    nombre_modelo = fields.Char(
 
        compute="_compute_nombre_model",
    )

    def _compute_id_model(self):
        context = dict(self.env.context or {})
        id_producto = context.get('producto')
        self.id_modelo = id_producto
    def _compute_nombre_model(self):
        context = dict(self.env.context or {})
        modelo_producto = context.get('modelo_producto')
        self.nombre_modelo = modelo_producto



    def action_guardar(self):
        _logger.info('---------- action_guardar')
        context = dict(self.env.context or {})
        id_producto = context.get('producto')
        modelo_producto = context.get('modelo_producto')
    
        if len(self.fases) == 0:
            raise ValidationError('Tiene que introducir fases')
        for fase in self.fases:
            if fase.minutos == 0:
                raise ValidationError('Es necesario introducir la cantidad de minutos en las fases.')

        producto = False
        if modelo_producto == 'product.product':
            producto_producto = self.env['product.product'].search([('id', '=', id_producto)], limit = 1)
            if not producto_producto:
                return
            producto = producto_producto.product_tmpl_id
            
        
        if modelo_producto == 'product.template':
            producto = self.env['product.template'].search([('id', '=', id_producto)], limit = 1)
         
        
        
        if not producto:
            return
        
        componentes = []
        componentes_unitario = []
        superficie = 0
        peso = 0
        peso_materia_prima = 0
        if len(self.componentes) > 0:
            peso_materia_prima = self.componentes[0].producto.weight
        if self.largo and self.ancho and self.altura:
            #Superficie = ((L/1000) x (A/1000) x 2) + ((L/1000) x (H/1000) x 2) + ((A/1000) x (H/1000) x 2) = un dato que seria metros cuadrados
            #Peso = (L/1000) x (A/1000) x H x Peso especifico (este campo debería de ser el campo base de odoo de peso ) = kg de producto
            superficie = ((self.largo/1000) * (self.ancho/1000) * 2) + ((self.largo/1000) * (self.altura/1000) * 2) + ((self.ancho/1000) * (self.altura/1000) * 2)
            peso = (self.largo/1000) * (self.ancho/1000) * self.altura * peso_materia_prima
        elif self.largo and self.diametro:
            #Superficie = (PI x (radio cuadrado / 1000) x 2) + (2 x PI x (Radio/1000) x L) = metros cuadrados
            #Peso =  PI (3,1416) x (Radio al cuadrado / 1000) x largo/1000 x Peso especifico
            radio_cuadrado = (self.diametro / 2) ** 2
            radio = (self.diametro / 2)
            superficie = ((math.pi * (radio_cuadrado / 1000) * 2) + (2 * math.pi * (radio/1000) * self.largo)) / 1000
            peso = math.pi * (radio_cuadrado / 1000) * self.largo/1000 * peso_materia_prima
        for componente_aux in self.componentes:
            componente = self.env['javier_ramos_taller_simple.componentes'].create({
                'producto': componente_aux.producto.id,
                'precio_unidad': componente_aux.precio_unidad,
                'cantidad': peso,
                'total': componente_aux.precio_unidad * peso
            })
            componentes.append(componente.id)
        for componente_aux in self.componentes_conjunto:
            precio_unidad = 0
            if producto and producto.sale_order_line:
                precio_unidad = componente_aux.producto.calcular_precio_venta((producto.sale_order_line.product_uom_qty * componente_aux.cantidad))
            
            else:
                precio_unidad = componente_aux.producto.standard_price
            componente = self.env['javier_ramos_taller_simple.componentes_unitario'].create({
                'producto_principal': producto.id,
                'producto': componente_aux.producto.id,
                'precio_unidad': precio_unidad,
                'cantidad': componente_aux.cantidad,
                'total': precio_unidad * componente_aux.cantidad
            })
            componentes_unitario.append(componente.id)
        servicios = []
        servicios_conjunto = []
        for componente_aux in self.servicios:
            precio_servicio = producto.calcular_precio_servicio(superficie=superficie, servicio=componente_aux)
            componente = self.env['javier_ramos_taller_simple.servicios'].create({
                'precio_unidad': precio_servicio,
                'producto': componente_aux.producto.id,
                'tiempo_esperado': componente_aux.tiempo_esperado,
                'cantidad': superficie,
                'total': precio_servicio * superficie
            })
            servicios.append(componente.id)
        for componente_aux in self.servicios_conjunto:
            componente = self.env['javier_ramos_taller_simple.servicios_conjunto'].create({
                'precio_unidad': componente_aux.precio_unidad,
                'producto': componente_aux.producto.id,
                'tiempo_esperado': componente_aux.tiempo_esperado,
            })
            servicios_conjunto.append(componente.id)
        producto.write({
            'componentes' : [(6, 0, componentes)],
            'servicios' : [(6, 0, servicios)],
            'componentes_unitario' : [(6, 0, componentes_unitario)],
            'servicios_conjunto' : [(6, 0, servicios_conjunto)],
        })
            
        fases = []
        for fase_aux in self.fases:
            fase = self.env['javier_ramos_taller_simple.fases'].create({
                'operacion': fase_aux.operacion,
                'num_fases': fase_aux.num_fases,
                'centro_trabajo': fase_aux.centro_trabajo.id,
                'minutos': fase_aux.minutos,
                'ignorar_preparacion_limpieza': fase_aux.ignorar_preparacion_limpieza,
            })
            fases.append(fase.id)
        producto.write({
            'fases' : [(6,0, fases)]
        })
            
        producto.write({
            'tipo_producto' : self.tipo_producto,
            'altura': self.altura,
            'largo': self.largo,
            'ancho': self.ancho,
            'diametro': self.diametro,
            'superficie': superficie,
            'peso': peso,
        })



    
        