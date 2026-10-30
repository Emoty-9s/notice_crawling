"""Small standard-library HTML tree, scoped lookup and explicit shape errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser

from src.core.normalizer import html_to_content_text


class StructureError(ValueError):
    """An expected list/detail structure is absent, ambiguous or incomplete."""


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    def find(self, tag=None, *, cls=None, id=None, attr=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if ((tag is None or child.tag == tag)
                    and (cls is None or set(cls.split()) <= set(child.attrs.get('class', '').split()))
                    and (id is None or child.attrs.get('id') == id)
                    and (attr is None or all(child.attrs.get(k) == v for k, v in attr.items()))):
                    result.append(child)
                result.extend(child.find(tag, cls=cls, id=id, attr=attr))
        return result

    def one(self, tag=None, **conditions):
        matches = self.find(tag, **conditions)
        if len(matches) != 1:
            raise StructureError(f'expected one {tag} {conditions}, found {len(matches)}')
        return matches[0]

    def elements(self, *tags):
        return [c for c in self.children if isinstance(c, Node) and (not tags or c.tag in tags)]

    def html(self):
        attrs = ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in self.attrs.items())
        content = ''.join(c.html() if isinstance(c, Node) else escape(c) for c in self.children)
        if self.tag == 'document':
            return content
        return f'<{self.tag}{attrs}>{content}</{self.tag}>'

    def text(self):
        return html_to_content_text(self.html())


class _Tree(HTMLParser):
    voids = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or '' for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.voids:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.voids:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        self.stack[-1].children.append(text)


def parse_html(html: str) -> Node:
    parser = _Tree()
    parser.feed(html)
    parser.close()
    return parser.root


def field_value(scope: Node, label: str) -> str | None:
    """Read adjacent th/td, dt/dd or strong/text fields observed in fixtures."""
    values = []
    for node in scope.find():
        if node.tag not in ('th', 'dt', 'strong') or node.text() != label:
            continue
        if node.tag == 'strong':
            text = node.parent.text()
            values.append(text[len(label):].strip())
        else:
            siblings = node.parent.elements()
            index = siblings.index(node)
            if index + 1 < len(siblings) and siblings[index + 1].tag in ('td', 'dd'):
                values.append(siblings[index + 1].text())
    if len(values) > 1:
        raise StructureError(f'ambiguous field: {label}')
    return values[0] if values else None
