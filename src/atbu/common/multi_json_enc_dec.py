# Copyright 2022 Ashley R. Thomas
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
r"""Support json encoding/decoding of multiple classes via use of single
instance of MultiEncoderDecoder.
"""
import json
from typing import Callable


class MultiEncoderDecoder:
    """An instance of MultiEncoderDecoder can json encode/decode one or more
    classes. Call add_def() to inform this instance of each such class.
    """

    class Definition:
        def __init__(
            self,
            class_type: type,
            to_dict_method: Callable[[object], dict],
            from_dict_method: Callable[[object, object], None],
            constructor_arg_names: list[str],
        ):
            self.class_type = class_type
            self.to_dict_method = to_dict_method
            self.from_dict_method = from_dict_method
            self.constructor_arg_names = constructor_arg_names

    def __init__(self):
        self.enc_dec_defs = list()

    def add_def(
        self,
        class_type: type,
        to_dict_method: Callable[[object], dict],
        from_dict_method: Callable[[object, object], None],
        constructor_arg_names: list[str],
    ):
        """Inform this instance to include the specified class
        in its encoding/decoding efforts.
        """
        self.enc_dec_defs.append(
            MultiEncoderDecoder.Definition(
                class_type=class_type,
                to_dict_method=to_dict_method,
                from_dict_method=from_dict_method,
                constructor_arg_names=constructor_arg_names,
            )
        )

    def get_json_encoder_class(self):
        """Return a json.JSONEncoder to use is json.* calls
        accepting an encoder.
        """

        class CustomEncoder(json.JSONEncoder):
            owner = self

            def default(self, o):
                d = CustomEncoder.owner._default(o)  # pylint: disable=protected-access
                if not d:
                    return json.JSONEncoder.default(self, o)
                return d

        return CustomEncoder

    def get_json_decoder_class(self):
        """Returns a json.JSONDecoder to use in json.* calls
        accepting a decoder.
        """

        class CustomDecoder(json.JSONDecoder):
            owner = self

            def __init__(self, *args, **kwargs):
                json.JSONDecoder.__init__(
                    self, object_hook=self.object_hook, *args, **kwargs
                )

            def object_hook(self, obj):  # pylint: disable=method-hidden,no-self-use
                return CustomDecoder.owner._object_hook(
                    obj
                )  # pylint: disable=protected-access

        return CustomDecoder

    def _default(self, obj):
        enc_dec_def: MultiEncoderDecoder.Definition
        for enc_dec_def in self.enc_dec_defs:
            if isinstance(obj, enc_dec_def.class_type):
                v = enc_dec_def.to_dict_method(obj)
                if isinstance(v, dict):
                    v["_type"] = enc_dec_def.class_type.__name__
                return v
        return None

    def _object_hook(self, obj):
        if "_type" not in obj:
            return obj
        obj_type_str = obj["_type"]
        enc_dec_def: MultiEncoderDecoder.Definition
        for enc_dec_def in self.enc_dec_defs:
            if enc_dec_def.class_type.__name__ == obj_type_str:
                args = [obj[k] for k in enc_dec_def.constructor_arg_names]
                o = enc_dec_def.class_type(*args)
                enc_dec_def.from_dict_method(o, obj)
                return o
        return obj
