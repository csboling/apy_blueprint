import re

from markdown import Markdown
from flask.ext.restplus import reqparse, marshal_with, Resource
import flask.ext.restplus.fields as model_fields

from funcy import compose, partial, rpartial, constantly

class Parser:
  def __init__(self, api):
    self.api = api

  @property
  def typename_map(self):
    return {
      'number': {
        'marshaler':
          lambda f: model_fields.Float(),
        'pytype':
          int, #float,
      },
      'boolean': {
        'marshaler':
          lambda f: model_fields.Boolean(),
        'pytype':
          bool,
      },
      'string': {
        'marshaler':
          lambda f: model_fields.String(),
        'pytype':
          str,
      },
      'array': {
        'marshaler':
          self.array_to_field,
        'pytype':
          list,
      },
      'object': {
        'marshaler':
          self.object_to_field,
        'pytype':
          dict,
      },
      'enum': {
        'marshaler':
          self.enum_to_field,
      },
    }

  def lookup_datastruct(self, typename):
    try:
      structure = self.api._data_structures[typename]
    except KeyError:
      print('data structure {} not defined'.format(typename))
      raise
    else:
      return self.object_to_field(structure)

  def array_to_field(self, field):
    inside = field.extract_array_subtype(field.type)
    return compose(
      model_fields.List,
      self.get_typename_marshaler(inside)
    )(field)

  def object_to_field(self, field):
    return model_fields.Nested(
      dict(
        map(self.parse_field, field.value)
      )
    )

  def enum_to_field(self, field):
    return model_fields.String(enum=[f.name for f in field.value])

  def get_typename_marshaler(self, typename):
    try:
      return self.typename_map[typename]['marshaler']
    except KeyError:
      return (lambda field: self.lookup_datastruct(typename))

  def parse_field(self, field):
    outer_typename = field.type.split('[', 1)[0]
    typename_marshaler = self.get_typename_marshaler(outer_typename)
    return (field.name, typename_marshaler(field))

  def add_parameters(self, impl, parameters):
    for parameter in parameters:
      impl.parser.add_argument(parameter.name,
        type=self.typename_map[parameter.type]['pytype'],
        required=bool(parameter.required),
        help=parameter.description,
        default=parameter.value
      )
      impl.parameters[parameter.name] = parameter

  urlparam_typemap = {
    'string': 'string',
    'number': 'int',
  }

  def mkuri(self, uri, parameters):
    flask_uri = ''
    path = re.compile(r'((?<=^)|(?<=}))(?P<before>.*){(?P<arg>\w+)}')
    for match in path.finditer(uri):
      arg = match.group('arg')
      param = parameters[arg]
      flask_uri += ''.join([
        match.group('before'),
        '<{}:{}>'.format(
          self.urlparam_typemap[param.type],
          arg
        ),
      ])
    return (flask_uri or uri)



class Schema:
  def __init__(self, api, apib):
    self.api = api

    markdown_parser = Markdown(extensions=['plueprint'])
    markdown_parser.set_output_format('apiblueprint')
    with open(apib, 'r') as f:
      self.api_spec = markdown_parser.convert(f.read())
    self.parser = Parser(self.api_spec)
    self.routes = {
      resource.uri_template.uri: resource
      for resource in self.api_spec.resources
    }

  def decorate_method(self, impl, method):
    print('decorating {}::{}'.format(impl, method))
    try:
      undecorated_method = getattr(impl, method)
    except AttributeError:
      print(
        'class {} does not implement method {}'.format(
          impl.__name__, method
        )
      )
      raise
    setattr(
      impl,
      method,
      compose(
        self.api.doc(parser=impl.parser),
        marshal_with(impl.model)
      )(undecorated_method)
    )

  def get_model(self, action):
    fields = {}
    for response in action.responses[200]:
      fields.update(dict(map(self.parser.parse_field, response.attributes)))
    return fields

  def decorate(self, resource, uri):
    def decorator(undecorated):
      impl = type(
        undecorated.__name__,
        (Resource,) + undecorated.__bases__,
        dict(undecorated.__dict__)
      )

      impl.parser = reqparse.RequestParser()

      impl.parameters = {}
      if resource.parameters:
        self.parser.add_parameters(impl, resource.parameters)

      for action in resource._actions.values():
        impl.model = self.get_model(action)
        self.decorate_method(impl, action.request_method.lower())


      flask_uri = self.parser.mkuri(uri, impl.parameters)
      print('adding {} to {} at {}'.format(impl, self.api, flask_uri))
      self.api.add_resource(impl, flask_uri)

      return impl
    return decorator

  def at(self, uri):
    try:
      resource = self.routes[uri]
    except KeyError:
      print('no resource specified at {}'.format(uri))
      raise
    else:
      return self.decorate(resource, uri)
