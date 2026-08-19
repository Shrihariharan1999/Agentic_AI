from app.models.factory import model_factory


def test_nvidia_model():
    model = model_factory.get("planner")
    response = model.invoke("Explain software testing in one sentence.")
    print(response.content)
    assert response.content