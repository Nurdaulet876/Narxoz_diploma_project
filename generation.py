import pandas as pd
import numpy as np

n_per_group = 50
total_students = n_per_group * 4

group1 = pd.DataFrame({
    'total_time_seconds': np.random.normal(3000, 400, n_per_group),
    'total_clicks': np.random.normal(50, 5, n_per_group),
    'unique_materials_viewed': np.random.randint(11, 15, n_per_group),
    'submitted_assignments_count': 3,
    'total_score': np.random.normal(90, 5, n_per_group)
})

group2 = pd.DataFrame({
    'total_time_seconds': np.random.normal(2000, 300, n_per_group),
    'total_clicks': np.random.normal(30, 5, n_per_group),
    'unique_materials_viewed': np.random.randint(7, 11, n_per_group),
    'submitted_assignments_count': np.random.randint(2, 4, n_per_group),
    'total_score': np.random.normal(70, 7, n_per_group)
})

group3 = pd.DataFrame({
    'total_time_seconds': np.random.normal(600, 150, n_per_group),
    'total_clicks': np.random.normal(10, 4, n_per_group),
    'unique_materials_viewed': np.random.randint(3, 7, n_per_group),
    'submitted_assignments_count': np.random.randint(1, 3, n_per_group),
    'total_score': np.random.normal(30, 10, n_per_group)
})

group4 = pd.DataFrame({
    'total_time_seconds': np.random.normal(90, 30, n_per_group),
    'total_clicks': np.random.normal(2, 2, n_per_group),
    'unique_materials_viewed': np.random.randint(0, 3, n_per_group),
    'submitted_assignments_count': np.random.randint(0, 2, n_per_group),
    'total_score': np.random.normal(5, 5, n_per_group)
})

df = pd.concat([group1, group2, group3, group4]).clip(0, None).astype(int)

df['total_score'] = df['total_score'].clip(0, 100)
df = df.sample(frac=1).reset_index(drop=True)

df.insert(0, 'student_id', range(8, 8 + total_students))
df.insert(1, 'student_name', [f"Student {i}" for i in range(1, total_students + 1)])

df.to_csv('canvas_export.csv', index=False)
print(df.head())