from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any

from ctools.utils import SingletonMetaclass


class IEnvElement(ABC):

    @abstractmethod
    def __repr__(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def info(self) -> Any:
        raise NotImplementedError


class EnvElement(IEnvElement):
    info_template = namedtuple('EnvElementInfo', ['shape', 'value', 'to_agent_processor', 'from_agent_processor'])
    _instance = None
    _name = 'EnvElement'

    def __init__(self, *args, **kwargs) -> None:
        # placeholder
        # self._shape = None
        # self._value = None
        # self._to_agent_processor = None
        # self._from_agent_processor = None
        self._init(*args, **kwargs)
        self._check()

    @abstractmethod
    def _init(*args, **kwargs) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return '{}: {}'.format(self._name, self._details())

    @abstractmethod
    def _details(self) -> str:
        raise NotImplementedError

    def _check(self) -> None:
        flag = [
            hasattr(self, '_shape'),
            hasattr(self, '_value'),
            hasattr(self, '_to_agent_processor'),
            hasattr(self, '_from_agent_processor'),
        ]
        assert all(flag), 'this class {} is not a legal subclass of EnvElement({})'.format(self.__class__, flag)

    @property
    def info(self) -> 'EnvElement.info_template':
        return self.info_template(
            shape=self._shape,
            value=self._value,
            to_agent_processor=self._to_agent_processor,
            from_agent_processor=self._from_agent_processor
        )
