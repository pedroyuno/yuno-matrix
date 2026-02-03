"""
Utilities for converting Pydantic schemas to UI-friendly metadata.

This module provides functions to extract field information from Pydantic models
and format them for use in dynamic form generation.
"""

from typing import Any, Dict, List, Optional, Type, get_args, get_origin
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefinedType
from dataclasses import dataclass, field, asdict
import inspect


def _is_json_serializable(value: Any) -> bool:
    """Check if a value is JSON serializable."""
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_json_serializable(item) for item in value)
    if isinstance(value, dict):
        return all(_is_json_serializable(v) for v in value.values())
    return False


def _clean_value(value: Any) -> Any:
    """Clean a value for JSON serialization."""
    if isinstance(value, PydanticUndefinedType):
        return None
    if not _is_json_serializable(value):
        return None
    return value


@dataclass
class SchemaField:
    """Represents a single field in a schema for UI rendering."""
    name: str
    path: str  # Dot-notation path like "customer_payer.billing_address.city"
    type: str  # "string", "number", "boolean", "object", "array"
    label: str
    description: str = ""
    required: bool = False
    default: Any = None
    placeholder: str = ""
    options: Optional[List[str]] = None  # For enum/select fields
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_sensitive: bool = False  # For password-like fields
    group: str = "other"  # UI grouping
    children: Optional[List["SchemaField"]] = None  # For nested objects
    is_array: bool = False
    array_item_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values and empty lists."""
        result = {}
        for key, value in asdict(self).items():
            # Clean the value for JSON serialization
            cleaned = _clean_value(value)
            if cleaned is not None:
                if isinstance(cleaned, list) and len(cleaned) == 0:
                    continue
                if key == "children" and cleaned:
                    result[key] = [child if isinstance(child, dict) else asdict(child) for child in cleaned]
                else:
                    result[key] = cleaned
        return result


@dataclass
class FieldGroup:
    """A group of related fields for UI organization."""
    id: str
    label: str
    description: str = ""
    collapsed: bool = False
    required: bool = False
    fields: List[SchemaField] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "collapsed": self.collapsed,
            "required": self.required,
            "fields": [f.to_dict() for f in self.fields]
        }


def _get_python_type_name(annotation: Any) -> str:
    """Convert Python type annotation to a simple type string."""
    origin = get_origin(annotation)
    
    if origin is list or origin is List:
        args = get_args(annotation)
        if args:
            inner_type = _get_python_type_name(args[0])
            return f"array[{inner_type}]"
        return "array"
    
    if origin is Optional or origin is type(None):
        args = get_args(annotation)
        if args:
            return _get_python_type_name(args[0])
        return "string"
    
    if origin is not None:
        # Handle Union types
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if non_none_args:
            return _get_python_type_name(non_none_args[0])
    
    if annotation is str:
        return "string"
    elif annotation is int:
        return "integer"
    elif annotation is float:
        return "number"
    elif annotation is bool:
        return "boolean"
    elif hasattr(annotation, "__mro__") and BaseModel in annotation.__mro__:
        return "object"
    elif hasattr(annotation, "value"):  # Enum
        return "string"
    else:
        return "string"


def _is_pydantic_model(annotation: Any) -> bool:
    """Check if annotation is a Pydantic model class."""
    try:
        return inspect.isclass(annotation) and issubclass(annotation, BaseModel)
    except TypeError:
        return False


def _extract_field_info(
    field_name: str,
    field_info: FieldInfo,
    annotation: Any,
    path_prefix: str = "",
    depth: int = 0,
    max_depth: int = 5
) -> SchemaField:
    """Extract schema field information from a Pydantic field."""
    
    full_path = f"{path_prefix}.{field_name}" if path_prefix else field_name
    
    # Get json_schema_extra for UI hints
    extra = field_info.json_schema_extra or {}
    
    # Determine field type
    field_type = _get_python_type_name(annotation)
    
    # Check if it's an array
    is_array = field_type.startswith("array")
    array_item_type = None
    
    if is_array:
        # Extract inner type
        origin = get_origin(annotation)
        if origin is list or origin is List:
            args = get_args(annotation)
            if args:
                inner_annotation = args[0]
                array_item_type = _get_python_type_name(inner_annotation)
    
    # Get nested type for Optional[SomeModel]
    actual_annotation = annotation
    origin = get_origin(annotation)
    if origin is Optional or origin is type(None):
        args = get_args(annotation)
        if args:
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                actual_annotation = non_none[0]
    
    # Handle Union types
    if origin is not None and not (origin is list or origin is List):
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if non_none_args:
            actual_annotation = non_none_args[0]
    
    # Build the field
    schema_field = SchemaField(
        name=field_name,
        path=full_path,
        type=field_type if not is_array else "array",
        label=extra.get("ui_label", field_name.replace("_", " ").title()),
        description=field_info.description or "",
        required=extra.get("ui_required", False) or field_info.is_required(),
        default=_clean_value(field_info.default),
        placeholder=extra.get("ui_placeholder", ""),
        options=extra.get("ui_options"),
        is_sensitive=extra.get("ui_sensitive", False),
        group=extra.get("ui_group", "other"),
        is_array=is_array,
        array_item_type=array_item_type
    )
    
    # Extract validation constraints
    metadata = field_info.metadata or []
    for meta in metadata:
        if hasattr(meta, "min_length"):
            schema_field.min_length = meta.min_length
        if hasattr(meta, "max_length"):
            schema_field.max_length = meta.max_length
        if hasattr(meta, "ge"):
            schema_field.min_value = meta.ge
        if hasattr(meta, "le"):
            schema_field.max_value = meta.le
        if hasattr(meta, "gt"):
            schema_field.min_value = meta.gt
    
    # Check for min/max in field_info directly
    if hasattr(field_info, "min_length") and field_info.min_length is not None:
        schema_field.min_length = field_info.min_length
    if hasattr(field_info, "max_length") and field_info.max_length is not None:
        schema_field.max_length = field_info.max_length
    
    # Process nested objects if within depth limit
    if depth < max_depth and _is_pydantic_model(actual_annotation):
        schema_field.type = "object"
        schema_field.children = []
        
        for nested_name, nested_field_info in actual_annotation.model_fields.items():
            nested_annotation = actual_annotation.__annotations__.get(nested_name, str)
            child = _extract_field_info(
                nested_name,
                nested_field_info,
                nested_annotation,
                full_path,
                depth + 1,
                max_depth
            )
            schema_field.children.append(child)
    
    # Handle arrays of objects
    if is_array and array_item_type == "object":
        origin = get_origin(actual_annotation)
        if origin is list or origin is List:
            args = get_args(actual_annotation)
            if args and _is_pydantic_model(args[0]):
                item_model = args[0]
                schema_field.children = []
                for nested_name, nested_field_info in item_model.model_fields.items():
                    nested_annotation = item_model.__annotations__.get(nested_name, str)
                    child = _extract_field_info(
                        nested_name,
                        nested_field_info,
                        nested_annotation,
                        f"{full_path}[]",
                        depth + 1,
                        max_depth
                    )
                    schema_field.children.append(child)
    
    return schema_field


def get_schema_metadata(
    model: Type[BaseModel],
    max_depth: int = 5
) -> Dict[str, Any]:
    """
    Extract complete schema metadata from a Pydantic model.
    
    Returns a dictionary containing:
    - fields: List of field definitions with nested structure
    - groups: Suggested UI groupings
    - required_fields: List of required field paths
    
    Args:
        model: Pydantic model class to extract metadata from
        max_depth: Maximum nesting depth to process
        
    Returns:
        Dictionary with schema metadata for UI generation
    """
    fields = []
    required_fields = []
    
    for field_name, field_info in model.model_fields.items():
        annotation = model.__annotations__.get(field_name, str)
        
        schema_field = _extract_field_info(
            field_name,
            field_info,
            annotation,
            path_prefix="",
            depth=0,
            max_depth=max_depth
        )
        
        fields.append(schema_field.to_dict())
        
        if schema_field.required:
            required_fields.append(schema_field.path)
    
    return {
        "model_name": model.__name__,
        "description": model.__doc__ or "",
        "fields": fields,
        "required_fields": required_fields
    }


def get_field_groups(model: Type[BaseModel]) -> List[FieldGroup]:
    """
    Organize schema fields into logical UI groups.
    
    Args:
        model: Pydantic model class
        
    Returns:
        List of FieldGroup objects for UI rendering
    """
    # Define the groups with their properties
    group_definitions = {
        "required": FieldGroup(
            id="required",
            label="Required Fields",
            description="These fields are required for the payment request",
            collapsed=False,
            required=True
        ),
        "payment_method": FieldGroup(
            id="payment_method",
            label="Payment Method",
            description="Payment method and card details",
            collapsed=False,
            required=True
        ),
        "customer_payer": FieldGroup(
            id="customer_payer",
            label="Customer Information",
            description="Customer and billing details",
            collapsed=True
        ),
        "additional_data": FieldGroup(
            id="additional_data",
            label="Additional Data",
            description="Order items and provider-specific data",
            collapsed=True
        ),
        "checkout": FieldGroup(
            id="checkout",
            label="Checkout Configuration",
            description="Checkout page customization",
            collapsed=True
        ),
        "fraud": FieldGroup(
            id="fraud",
            label="Fraud Screening",
            description="Fraud detection settings",
            collapsed=True
        ),
        "subscription": FieldGroup(
            id="subscription",
            label="Subscription",
            description="Recurring payment configuration",
            collapsed=True
        ),
        "metadata": FieldGroup(
            id="metadata",
            label="Metadata",
            description="Custom key-value tags",
            collapsed=True
        ),
        "optional": FieldGroup(
            id="optional",
            label="Other Options",
            description="Additional optional settings",
            collapsed=True
        ),
        "other": FieldGroup(
            id="other",
            label="Other",
            description="Other fields",
            collapsed=True
        )
    }
    
    # Extract fields and assign to groups
    for field_name, field_info in model.model_fields.items():
        annotation = model.__annotations__.get(field_name, str)
        schema_field = _extract_field_info(field_name, field_info, annotation)
        
        group_id = schema_field.group
        if group_id not in group_definitions:
            group_id = "other"
        
        group_definitions[group_id].fields.append(schema_field)
    
    # Return only groups that have fields, in order
    ordered_groups = ["required", "payment_method", "customer_payer", "additional_data", 
                      "optional", "checkout", "fraud", "subscription", "metadata", "other"]
    
    result = []
    for group_id in ordered_groups:
        if group_id in group_definitions and group_definitions[group_id].fields:
            result.append(group_definitions[group_id])
    
    return result


def schema_to_json(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Generate a complete JSON representation of the schema for API response.
    
    This is the main function to call for getting schema data for the UI.
    
    Args:
        model: Pydantic model class
        
    Returns:
        Dictionary with complete schema data including fields and groups
    """
    metadata = get_schema_metadata(model)
    groups = get_field_groups(model)
    
    return {
        "schema": metadata,
        "groups": [g.to_dict() for g in groups],
        "example": model.model_config.get("json_schema_extra", {}).get("example", {})
    }
