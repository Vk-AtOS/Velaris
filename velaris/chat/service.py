"""ChatService: the one object the API and the assistant talk to.

    ChatCore        plumbing: caller, policy check, trace, write-then-emit
    ChannelsMixin   channels, members, register/events, read cursors, pins, drafts
    MessagesMixin   send, edit, delete, react, history, search
    FilesMixin      attachments
    LinksMixin      optional link previews (off)
    ComplianceMixin export, hold, retention, erasure

Every method takes the Caller first and nothing else names who is acting.
"""
from __future__ import annotations

from velaris.chat.channels import ChannelsMixin
from velaris.chat.compliance import ComplianceMixin
from velaris.chat.files import FilesMixin
from velaris.chat.links import LinksMixin
from velaris.chat.messages import MessagesMixin


class ChatService(ChannelsMixin, MessagesMixin, FilesMixin, LinksMixin, ComplianceMixin):
    pass
