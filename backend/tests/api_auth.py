def authenticate(client,username="test_admin",password="PrototypeTestAdmin!123"):
    response=client.post("/api/v1/auth/token",json={"username":username,"password":password})
    assert response.status_code==200,response.text
    client.headers.update({"Authorization":f"Bearer {response.json()['access_token']}"})
    return response.json()
