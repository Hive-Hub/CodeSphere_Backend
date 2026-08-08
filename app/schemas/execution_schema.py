from marshmallow import Schema, fields, validate

class CodeExecutionRequestSchema(Schema):
    """Validation schema for online code execution requests."""
    language = fields.String(
        required=True,
        validate=validate.OneOf(["python", "py", "python3", "c", "java"])
    )
    code = fields.String(required=True, validate=validate.Length(min=1, max=50000))
    stdin = fields.String(required=False, load_default="")

class CodeExecutionResponseSchema(Schema):
    """Response schema for online code execution results."""
    success = fields.Boolean()
    language = fields.String()
    stdout = fields.String()
    stderr = fields.String()
    exit_code = fields.Integer()
    output = fields.String()
