
from abc import ABC, abstractmethod

class Repository(ABC):

    @abstractmethod
    def save(self, entity):
        raise NotImplementedError

    @abstractmethod
    def get(self, entity_id):
        raise NotImplementedError

    @abstractmethod
    def list(self):
        raise NotImplementedError

