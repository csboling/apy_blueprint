from markdown import Markdown
import flask_restful.reqparse
from flask_restplus import marshal_with
import flask_restplus.fields as model_fields

from funcy import compose, partial, rpartial, constantly

class Parser:
  def __init__(self, api):
    self.api = api

  @property
  def typename_map(self):
    return {
      'number':  lambda f: model_fields.Float(),
      'boolean': lambda f: model_fields.Boolean(),
      'string':  lambda f: model_fields.String(),
      'array':   self.array_to_field,
      'object':  self.object_to_field,
      'enum':    self.enum_to_field
    }

  def lookup_datastruct(self, typename):
    try:
      structure = self.api._data_structures[typename]
    except KeyError:
      import pdb; pdb.set_trace()
    else:
      print('found {}'.format(structure))
      return self.object_to_field(structure) #map(self.parse_field, field.value)

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
      return self.typename_map[typename]
    except KeyError:
      return (lambda field: self.lookup_datastruct(typename))

  def parse_field(self, field):
    outer_typename = field.type.split('[', 1)[0]
    typename_marshaler = self.get_typename_marshaler(outer_typename)
    ret = (field.name, typename_marshaler(field))
    # print(ret)
    return ret

class Schema:
  def __init__(self, apib):
    markdown_parser = Markdown(extensions=['plueprint'])
    markdown_parser.set_output_format('apiblueprint')
    with open(apib, 'r') as f:
      self.api = markdown_parser.convert(f.read())
    self.parser = Parser(self.api)
    self.routes = {
      resource.uri: resource
      for resource in self.api.resources
    }

  @staticmethod
  def decorate_method(impl, method):
    try:
      undecorated_method = getattr(impl, method)
    except AttributeError:
      print(
        'class {} does not implement method {}'.format(
          impl.__name__, method
        )
      )
      raise

    print(impl.fields)

    setattr(
      impl,
      method,
      marshal_with(impl.fields)(undecorated_method)
    )

  @staticmethod
  def add_parameters(parser, parameters):
    for parameter in parameters:
      import pdb; pdb.set_trace()
      parser.add_argument(
        parameter.name,
        dest=parameter.name
      )

  def get_fields(self, action):
    fields = {}
    for response in action.responses[200]:
      fields.update(dict(map(self.parser.parse_field, response.attributes)))
    return fields

  def decorate(self, resource):
    def decorator(impl):
      impl.parser = flask_restful.reqparse.RequestParser()
      for action in resource._actions.values():
        if action.parameters:
          self.add_parameters(impl.parser, action.parameters)
        impl.fields = self.get_fields(action)
        print(impl.fields)
        self.decorate_method(impl, action.request_method.lower())
      return impl
    return decorator

  def at(self, uri):
    try:
      resource = self.routes[uri]
    except KeyError:
      print('no resource specified at {}'.format(uri))
      raise
    else:
      return self.decorate(resource)
