from datetime import datetime
import enum
from io import BytesIO
from typing import Optional, List
from xml.etree.ElementTree import Element

import attr
from defusedxml.ElementTree import parse

from .utils import get_child, get_text, get_datetime, FeedParseError, ns


class AtomTextType(enum.Enum):
    text = "text"
    html = "html"
    xhtml = "xhtml"


@attr.s
class AtomTextConstruct:
    text_type: str = attr.ib()
    lang: Optional[str] = attr.ib()
    value: str = attr.ib()


@attr.s
class AtomEntry:
    title: AtomTextConstruct = attr.ib()
    id_: str = attr.ib()

    # Should be mandatory but many feeds use published instead
    updated: Optional[datetime] = attr.ib()

    authors: List['AtomPerson'] = attr.ib()
    contributors: List['AtomPerson'] = attr.ib()
    links: List['AtomLink'] = attr.ib()
    categories: List['AtomCategory'] = attr.ib()
    published: Optional[datetime] = attr.ib()
    rights: Optional[AtomTextConstruct] = attr.ib()
    summary: Optional[AtomTextConstruct] = attr.ib()
    content: Optional[AtomTextConstruct] = attr.ib()
    source: Optional['AtomFeed'] = attr.ib()


@attr.s
class AtomFeed:
    title: AtomTextConstruct = attr.ib()
    id_: str = attr.ib()

    # Should be mandatory but many feeds do not include it
    updated: Optional[datetime] = attr.ib()

    authors: List['AtomPerson'] = attr.ib()
    contributors: List['AtomPerson'] = attr.ib()
    links: List['AtomLink'] = attr.ib()
    categories: List['AtomCategory'] = attr.ib()
    generator: Optional['AtomGenerator'] = attr.ib()
    subtitle: Optional[AtomTextConstruct] = attr.ib()
    rights: Optional[AtomTextConstruct] = attr.ib()
    icon: Optional[str] = attr.ib()
    logo: Optional[str] = attr.ib()

    entries: List[AtomEntry] = attr.ib()


@attr.s
class AtomPerson:
    name: str = attr.ib()
    uri: Optional[str] = attr.ib()
    email: Optional[str] = attr.ib()


@attr.s
class AtomLink:
    href: str = attr.ib()
    rel: Optional[str] = attr.ib()
    type_: Optional[str] = attr.ib()
    hreflang: Optional[str] = attr.ib()
    title: Optional[str] = attr.ib()
    length: Optional[int] = attr.ib()


@attr.s
class AtomCategory:
    term: str = attr.ib()
    scheme: Optional[str] = attr.ib()
    label: Optional[str] = attr.ib()


@attr.s
class AtomGenerator:
    name: str = attr.ib()
    uri: Optional[str] = attr.ib()
    version: Optional[str] = attr.ib()


def _get_generator(element: Element, name,
                   optional: bool=False) -> Optional[AtomGenerator]:
    child = get_child(element, name, optional)
    if child is None:
        return None

    return AtomGenerator(
        child.text.strip(),
        child.attrib.get('uri'),
        child.attrib.get('version'),
    )


def _get_text_construct(element: Element, name,
                        optional: bool=False) -> Optional[AtomTextConstruct]:
    child = get_child(element, name, optional)
    if child is None:
        return None

    try:
        text_type = AtomTextType(child.attrib['type'])
    except KeyError:
        text_type = AtomTextType.text

    try:
        lang = child.lang
    except AttributeError:
        lang = None

    return AtomTextConstruct(
        text_type,
        lang,
        child.text.strip()
    )


def _get_person(element: Element) -> AtomPerson:
    return AtomPerson(
        get_text(element, 'feed:name'),
        get_text(element, 'feed:uri', optional=True),
        get_text(element, 'feed:email', optional=True)
    )


def _get_link(element: Element) -> AtomLink:
    length = element.attrib.get('length')
    length = int(length) if length else None
    return AtomLink(
        element.attrib['href'],
        element.attrib.get('rel'),
        element.attrib.get('type'),
        element.attrib.get('hreflang'),
        element.attrib.get('title'),
        length
    )


def _get_category(element: Element) -> AtomCategory:
    return AtomCategory(
        element.attrib['term'],
        element.attrib.get('scheme'),
        element.attrib.get('label'),
    )


def _get_entry(element: Element,
               default_authors: List[AtomPerson]) -> AtomEntry:
    root = element

    # Mandatory
    title = _get_text_construct(root, 'feed:title')
    id_ = get_text(root, 'feed:id')

    # Optional
    try:
        source = _parse_atom(get_child(root, 'feed:source'),
                             parse_entries=False)
    except FeedParseError:
        source = None
        source_authors = []
    else:
        source_authors = source.authors

    authors = [_get_person(e)
               for e in root.findall('feed:author', ns)] or default_authors
    authors = authors or default_authors or source_authors

    contributors = (
        [_get_person(e) for e in root.findall('feed:contributor', ns)]
    )
    links = [_get_link(e) for e in root.findall('feed:link', ns)]
    categories = [_get_category(e) for e in root.findall('feed:category', ns)]

    updated = get_datetime(root, 'feed:updated', optional=True)
    published = get_datetime(root, 'feed:published', optional=True)
    rights = _get_text_construct(root, 'feed:rights', optional=True)
    summary = _get_text_construct(root, 'feed:summary', optional=True)
    content = _get_text_construct(root, 'feed:content', optional=True)

    return AtomEntry(
        title,
        id_,
        updated,
        authors,
        contributors,
        links,
        categories,
        published,
        rights,
        summary,
        content,
        source
    )


def _parse_atom(root: Element, parse_entries: bool=True) -> AtomFeed:
    # Mandatory
    title = _get_text_construct(root, 'feed:title')
    id_ = get_text(root, 'feed:id')

    # Optional
    updated = get_datetime(root, 'feed:updated', optional=True)
    authors = [_get_person(e)
               for e in root.findall('feed:author', ns)]
    contributors = [_get_person(e)
                    for e in root.findall('feed:contributor', ns)]
    links = [_get_link(e)
             for e in root.findall('feed:link', ns)]
    categories = [_get_category(e)
                  for e in root.findall('feed:category', ns)]

    generator = _get_generator(root, 'feed:generator', optional=True)
    subtitle = _get_text_construct(root, 'feed:subtitle', optional=True)
    rights = _get_text_construct(root, 'feed:rights', optional=True)
    icon = get_text(root, 'feed:icon', optional=True)
    logo = get_text(root, 'feed:logo', optional=True)

    if parse_entries:
        entries = [_get_entry(e, authors)
                   for e in root.findall('feed:entry', ns)]
    else:
        entries = []

    atom_feed = AtomFeed(
        title,
        id_,
        updated,
        authors,
        contributors,
        links,
        categories,
        generator,
        subtitle,
        rights,
        icon,
        logo,
        entries
    )
    return atom_feed


def parse_atom_file(filename: str) -> AtomFeed:
    """Parse an Atom feed from a local XML file."""
    root = parse(filename).getroot()
    return _parse_atom(root)


def parse_atom_bytes(data: bytes) -> AtomFeed:
    """Parse an Atom feed from a byte-string containing XML data."""
    root = parse(BytesIO(data)).getroot()
    return _parse_atom(root)
