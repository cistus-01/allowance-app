from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.name = row['name']
        self.username = row['username']
        self.password_hash = row['password_hash']
        self.role = row['role']
        self.grade = row['grade']
        self.family_id = row['family_id'] if 'family_id' in row.keys() else None

    @property
    def is_parent(self):
        return self.role == 'parent'

    @property
    def is_child(self):
        return self.role == 'child'
