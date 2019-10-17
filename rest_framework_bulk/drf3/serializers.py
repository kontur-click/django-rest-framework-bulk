from __future__ import print_function, unicode_literals
import inspect

from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ListSerializer
from rest_framework.settings import api_settings
from rest_framework.utils import html
from rest_framework.fields import SkipField


__all__ = [
    'BulkListSerializer',
    'BulkSerializerMixin',
]


class BulkSerializerMixin(object):
    def to_internal_value(self, data):
        ret = super(BulkSerializerMixin, self).to_internal_value(data)

        id_attr = getattr(self.Meta, 'update_lookup_field', 'id')
        request_method = getattr(self.context['request'], 'method', '')

        # add update_lookup_field field back to validated data
        # since super by default strips out read-only fields
        # hence id will no longer be present in validated_data
        if all((isinstance(self.root, BulkListSerializer),
                id_attr,
                request_method in ('PUT', 'PATCH'))):
            id_field = self.fields[id_attr]
            id_value = id_field.get_value(data)

            ret[id_attr] = id_value

        return ret


class BulkListSerializer(ListSerializer):
    update_lookup_field = 'id'

    def update_or_create_instance(self, child, data, obj=None):
        model_serializer = child.__class__(instance=obj, data=data,
                                           context=self.context, partial=self.partial)
        model_serializer.is_valid()
        model_serializer.save()
        return model_serializer.instance

    def create(self, validated_data):
        return [
            self.update_or_create_instance(self.child, attrs)
            for attrs in validated_data
        ]

    def update(self, queryset, all_validated_data):
        id_attr = getattr(self.child.Meta, 'update_lookup_field', 'id')

        all_validated_data_by_id = {}
        for i in all_validated_data:
            key = i.get(id_attr)
            if not (bool(key) and not inspect.isclass(key)):
                raise ValidationError('')

            all_validated_data_by_id[str(key)] = i

        # since this method is given a queryset which can have many
        # model instances, first find all objects to update
        # and only then update the models
        objects_to_update = queryset.filter(**{
            '{}__in'.format(id_attr): list(all_validated_data_by_id.keys()),
        })

        if len(all_validated_data_by_id) != objects_to_update.count():
            raise ValidationError('Could not find all objects to update.')

        updated_objects = []

        for obj in objects_to_update:
            obj_id = str(getattr(obj, id_attr))
            obj_validated_data = all_validated_data_by_id.get(obj_id)

            # use model serializer to actually update the model
            # in case that method is overwritten
            updated_objects.append(
                self.update_or_create_instance(self.child, obj_validated_data,
                                               obj))

        return updated_objects

    def to_internal_value(self, data):
        """
        List of dicts of native values <- List of dicts of primitive datatypes.
        """
        if html.is_html_input(data):
            data = html.parse_html_list(data, default=[])

        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(
                input_type=type(data).__name__
            )
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            }, code='not_a_list')

        if not self.allow_empty and len(data) == 0:
            if self.parent and self.partial:
                raise SkipField()

            message = self.error_messages['empty']
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            }, code='empty')

        ret = []
        errors = []

        for item in data:
            try:
                self.child.instance = self.instance.get(id=item['id']) if self.instance else None
                self.child.initial_data = item
                validated = self.child.run_validation(item)
            except ValidationError as exc:
                errors.append(exc.detail)
            else:
                ret.append(validated)
                errors.append({})

        if any(errors):
            raise ValidationError(errors)

        return ret
