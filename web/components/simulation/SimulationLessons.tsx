"use client";

import type { SimulationLesson } from "../../lib/types";

type Props = {
  lessons: SimulationLesson[];
};

export function SimulationLessons({ lessons }: Props) {
  return (
    <div className="panel__card">
      <div className="panel__header">
        <h3>Lessons Learned</h3>
        <div className="panel__meta">
          {lessons.length > 0 && <span className="panel__badge">{lessons.length}</span>}
        </div>
      </div>
      {lessons.length === 0 ? (
        <p className="panel__empty">No lessons yet.</p>
      ) : (
        <div className="simulation__lessons-list">
          {lessons.map((lesson) => (
            <div key={lesson.id} className="simulation__lesson-item">
              <span>{lesson.lesson}</span>
              {lesson.created_at && (
                <span className="simulation__lesson-meta">
                  {new Date(lesson.created_at).toLocaleDateString()}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
