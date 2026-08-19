from pydantic import BaseModel, ConfigDict


def to_camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    """Base for all response models.

    Serialises camelCase so the TypeScript client can consume responses
    without a mapping layer, while Python code keeps snake_case.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )
