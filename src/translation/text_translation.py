"""Traduction FR -> EN des segments transcrits.

Deux parties séparées :
- HuggingFaceTranslator : charge un modèle et traduit UN texte (seul endroit qui dépend de torch).
- translate_segments : logique métier (validation, conservation des id/timestamps, ordre).
  Elle accepte n'importe quel objet possédant une méthode translate(text) -> str.
"""
from .translation_utils import validate_transcription_segments

# Choix documenté dans docs/translation_model_choice.md
DEFAULT_MODEL_NAME = "Helsinki-NLP/opus-mt-tc-big-fr-en"


class HuggingFaceTranslator:
    """Traducteur basé sur un modèle Hugging Face encodeur-décodeur (MarianMT, NLLB, M2M100).

    Pour MarianMT, src_lang et tgt_lang_token restent à None (le modèle ne fait que FR -> EN).
    Pour NLLB : src_lang="fra_Latn", tgt_lang_token="eng_Latn".
    Pour M2M100 : src_lang="fr", tgt_lang_token="__en__".
    """

    def __init__(self, model_name=DEFAULT_MODEL_NAME, src_lang=None, tgt_lang_token=None,
                 num_beams=4, max_new_tokens=256, device=None):
        # Imports ici : le reste du module (et ses tests) fonctionne sans torch installé.
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.generation_params = {"num_beams": num_beams, "max_new_tokens": max_new_tokens}

        tokenizer_kwargs = {"src_lang": src_lang} if src_lang else {}
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, **tokenizer_kwargs)

        # float32 imposé : même précision sur le Mac et sur Colab (sinon transformers 5
        # reprend la précision du fichier, ex. float16 pour tc-big).
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, dtype=torch.float32)
        self.model.to(self.device)
        self.model.eval()

        self.target_lang_id = None
        if tgt_lang_token:
            token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang_token)
            # Un code inconnu donne silencieusement <unk> : le modèle traduirait au hasard.
            if token_id == self.tokenizer.unk_token_id:
                raise ValueError(f"Code de langue inconnu pour {model_name} : {tgt_lang_token}")
            self.target_lang_id = token_id

    def translate(self, text):
        """Traduit un texte et retourne la meilleure traduction (str)."""
        return self._generate(text, num_return_sequences=1)[0]

    def translate_candidates(self, text, num_candidates=4):
        """Retourne jusqu'à num_candidates traductions différentes, de la plus probable à la moins probable.

        Ce sont les meilleures hypothèses du beam search : on ne peut pas en demander plus
        que num_beams.
        """
        if num_candidates > self.generation_params["num_beams"]:
            raise ValueError(f"num_candidates ({num_candidates}) ne peut pas dépasser num_beams "
                             f"({self.generation_params['num_beams']}).")
        candidates = self._generate(text, num_return_sequences=num_candidates)
        return list(dict.fromkeys(candidates))  # supprime les doublons en gardant l'ordre

    def _generate(self, text, num_return_sequences):
        import torch

        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        generation_kwargs = dict(self.generation_params, num_return_sequences=num_return_sequences)
        if self.target_lang_id is not None:
            generation_kwargs["forced_bos_token_id"] = self.target_lang_id

        with torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generation_kwargs)
        return [self.tokenizer.decode(ids, skip_special_tokens=True).strip() for ids in output_ids]


def translate_segments(segments, translator):
    """Traduit chaque segment et retourne une NOUVELLE liste au format de sortie du contrat.

    - Les segments d'entrée sont validés avant toute traduction.
    - id, start, end sont recopiés tels quels ; l'ordre est conservé.
    - Les champs supplémentaires de l'entrée (ex. infos Whisper) ne sont pas transmis.
    - La liste d'entrée n'est pas modifiée.
    """
    validate_transcription_segments(segments)

    translated_segments = []
    for segment in segments:
        try:
            translated_text = translator.translate(segment["text"])
        except Exception as error:
            # On ne masque pas l'erreur : on la relance en indiquant quel segment a échoué.
            raise RuntimeError(f"Échec de la traduction du segment id={segment['id']}") from error

        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError(f"Traduction vide pour le segment id={segment['id']}")

        translated_segments.append({
            "id": segment["id"],
            "start": segment["start"],
            "end": segment["end"],
            "original_text": segment["text"],
            "translated_text": translated_text,
        })

    return translated_segments
