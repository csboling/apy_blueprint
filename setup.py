from setuptools import setup, find_packages

setup(
  name = 'apy_blueprint',
  packages = [
    'apy_blueprint',
  ],
  install_requires = [
    'funcy',

    'flask',
    'flask-cors',
    'flask-swagger',
    'flask-restful',
    'flask-restplus',

    'plueprint',
  ]
)
