# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import datetime
from waitress import serve
from markdown import markdown
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import DBAPIError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from zope.sqlalchemy import ZopeTransactionExtension
from pyramid.config import Configurator
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.security import remember, forget
from cryptacular.bcrypt import BCRYPTPasswordManager


HERE = os.path.dirname(os.path.abspath(__file__))
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Entry(Base):
    __tablename__ = 'entries'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    title = sa.Column(sa.Unicode(128), nullable=False)
    text = sa.Column(sa.UnicodeText, nullable=False)
    date = sa.Column(sa.DateTime, nullable=False,
                     default=datetime.datetime.utcnow)

    def mark_down(self):
        colored_text = markdown(self.text, extensions=['codehilite'])
        return colored_text

    @classmethod
    def write(cls, title=None, text=None, session=None):
        if session is None:
            session = DBSession
        instance = cls(title=title, text=text)
        session.add(instance)
        return instance

    @classmethod
    def change(cls, title=None, eid=None, text=None, session=None):
        if session is None:
            session = DBSession
        instance = cls.one(eid)
        instance.title = title
        instance.text = text
        session.add(instance)
        return instance

    @classmethod
    def all(cls, session=None):
        if session is None:
            session = DBSession
        return session.query(cls).order_by(cls.date.desc()).all()

    @classmethod
    def one(cls, eid=None, session=None):
        if session is None:
            session = DBSession
        return session.query(cls).filter(cls.id == eid).one()

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://johnson:password@localhost:5432/learning-journal'
)


def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)


@view_config(route_name='newpost', renderer='templates/newpost.jinja2')
def newpost(request):
    return {}


@view_config(route_name='home', renderer='templates/lists.jinja2')
def list_view(request):
    entries = Entry.all()
    return {'entries': entries}


@view_config(route_name='details', renderer='templates/details.jinja2')
def details(request):
    entry = Entry.one(request.matchdict['id'])
    return {'entry': entry}


@view_config(route_name='edit', renderer='templates/edit.jinja2')
def edit(request):
    if request.authenticated_userid is not None:
        entry = Entry.one(request.matchdict['id'])
        return {'entry': entry}
    else:
        return HTTPFound(request.route_url('login'))


def new_post(request):
    if request.authenticated_userid is not None:
        return {}
    else:
        return HTTPFound(request.route_url('login'))


@view_config(route_name='add', request_method='POST')
def add_entry(request):
    if request.authenticated_userid is not None:
        title = request.params.get('title')
        text = request.params.get('text')
        Entry.write(title=title, text=text)
    return HTTPFound(request.route_url('home'))


@view_config(route_name='edit_post', request_method='POST')
def edit_post(request):
    if request.authenticated_userid is not None:
        title = request.params.get('title')
        text = request.params.get('text')
        eid = request.matchdict['id']
        Entry.change(eid=eid, title=title, text=text)
        return HTTPFound(request.route_url('home'))
    else:
        return HTTPFound(request.route_url('login'))


@view_config(context=DBAPIError)
def db_exception(context, request):
    from pyramid.response import Response
    response = Response(context.message)
    response.status_int = 500
    return response


@view_config(route_name='login', renderer="templates/login.jinja2")
def login(request):
    """authenticate a user by username/password"""
    username = request.params.get('username', '')
    error = ''
    if request.method == 'POST':
        error = "Login Failed"
        authenticated = False
        try:
            authenticated = do_login(request)
        except ValueError as e:
            error = str(e)

        if authenticated:
            headers = remember(request, username)
            return HTTPFound(request.route_url('home'), headers=headers)

    return {'error': error, 'username': username}


@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(request.route_url('home'), headers=headers)


def main():
    """Create a configured wsgi app"""
    settings = {}
    debug = os.environ.get('DEBUG', True)
    settings['reload_all'] = debug
    settings['debug_all'] = debug
    settings['auth.username'] = os.environ.get('AUTH_USERNAME', 'admin')
    manager = BCRYPTPasswordManager()
    settings['auth.password'] = os.environ.get('AUTH_PASSWORD',
                                               manager.encode('secret'))
    if not os.environ.get('TESTING', False):
        engine = sa.create_engine(DATABASE_URL)
        DBSession.configure(bind=engine)
    auth_secret = os.environ.get('JOURNAL_AUTH_SECRET', 'itsaseekrit')
    config = Configurator(
        settings=settings,
        authentication_policy=AuthTktAuthenticationPolicy(
            secret=auth_secret,
            hashalg='sha512'
        ),
        authorization_policy=ACLAuthorizationPolicy(),
    )
    config.include('pyramid_tm')
    config.include('pyramid_jinja2')
    config.add_static_view('static', os.path.join(HERE, 'static'))
    config.add_route('home', '/')
    config.add_route('add', '/add')
    config.add_route('login', '/login')
    config.add_route('newpost', '/newpost')
    config.add_route('logout', '/logout')
    config.add_route('edit', '/edit/{id}')
    config.add_route('edit_post', '/edit_post/{id}')
    config.add_route('details', '/details/{id}')
    config.scan()
    app = config.make_wsgi_app()
    return app


def do_login(request):
    username = request.params.get('username', None)
    password = request.params.get('password', None)
    if not (username and password):
        raise ValueError('both username and password are required')
    settings = request.registry.settings
    manager = BCRYPTPasswordManager()
    if username == settings.get('auth.username', ''):
        hashed = settings.get('auth.password', '')
        return manager.check(hashed, password)
    return False


if __name__ == '__main__':
    app = main()
    port = os.environ.get('PORT', 9093)
    serve(app, host='0.0.0.0', port=port)
