from marshmallow import Schema, fields, validate

class TeacherSessionCreateSchema(Schema):
    """Schema for validating teacher session creation requests."""
    teacher_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    teacher_email = fields.Email(required=True)
    college = fields.String(required=True, validate=validate.Length(min=1, max=150))
    department = fields.String(required=True, validate=validate.Length(min=1, max=100))
    subject = fields.String(required=True, validate=validate.Length(min=1, max=100))
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    language = fields.String(
        required=True,
        validate=validate.OneOf(["python", "c", "java"], error="Language must be one of: python, c, java")
    )
    mode = fields.String(
        required=True,
        validate=validate.OneOf(["practice", "problem_solving"], error="Mode must be practice or problem_solving")
    )

class StudentJoinSchema(Schema):
    """Schema for validating student session join requests."""
    session_code = fields.String(
        required=True,
        validate=[
            validate.Length(equal=6, error="Session code must be exactly 6 digits"),
            validate.Regexp(r"^\d{6}$", error="Session code must contain numeric digits only")
        ]
    )
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    roll_number = fields.String(required=True, validate=validate.Length(min=1, max=50))
    department = fields.String(required=True, validate=validate.Length(min=1, max=100))
    year = fields.String(required=True, validate=validate.Length(min=1, max=20))
    section = fields.String(required=True, validate=validate.Length(min=1, max=20))

class ProblemCreateSchema(Schema):
    """Schema for validating problem creation requests."""
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(required=True, validate=validate.Length(min=1))
    constraints = fields.String(required=False, load_default="")
    input_format = fields.String(required=False, load_default="")
    output_format = fields.String(required=False, load_default="")
    sample_input = fields.String(required=False, load_default="")
    sample_output = fields.String(required=False, load_default="")
    reference_solution = fields.String(required=False, load_default="")
