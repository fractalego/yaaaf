import unittest

from yaaf.components.agents.artefacts import ArtefactStorage, Artefact


class TestArtefactStorage(unittest.TestCase):
    def test_artefact_can_be_stored_and_retrieved(self):
        storage = ArtefactStorage()
        artefact = Artefact(
            model=None,
            data=None,
            code=None,
            description="Test artefact",
            image=None,
            type="test",
            id="test_id",
        )
        hash_key = "12345"
        storage.store_artefact(hash_key, artefact)
        retrieved_artefact = storage.retrieve_from_id(hash_key)
        self.assertEqual(retrieved_artefact.description, "Test artefact")
