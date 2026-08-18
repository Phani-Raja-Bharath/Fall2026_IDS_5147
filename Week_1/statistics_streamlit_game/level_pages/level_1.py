import numpy as np
import streamlit as st


def render(ctx):
    pid = ctx.pid
    st.header(ctx.STORY["levels"][1])
    ctx.show_youtube_resources("level_1")
    ctx.show_level_1_formulas()
    st.write(ctx.content_get(
        "level_copy.level_1_intro",
        "A team is studying student commute times. Look at the usual pattern below, then think about "
        "what might happen if one commute took a lot longer than normal.",
    ))

    data = [10, 15, 15, 20, 25, 30, 35]
    st.write(data)
    ctx.show_descriptive_stats(data)
    prediction = st.radio(
        ctx.content_get("level_copy.level_1_prediction", "Before you try it: what do you think will happen if we replace 35 with 600?"),
        ["Mean changes most", "Median changes most", "Mode changes most", "They change equally"],
        index=None,
        key="l1_prediction",
    )
    if prediction:
        ctx.record_completion_once(pid, 1, "L1_PREDICT", prediction)
        st.caption(f"Prediction recorded: {prediction}")

    st.subheader("Question 1")
    ctx.show_challenge_acknowledgement(pid, "L1_OUTLIER")
    outlier = st.number_input(
        ctx.content_get("level_copy.level_1_outlier_input", "Enter a **very large outlier** to replace the final commute time"),
        min_value=60,
        max_value=600,
        value=600,
        step=10,
        key="l1_outlier_value",
    )
    st.caption(ctx.content_get("level_copy.level_1_outlier_caption", "Try values like 90, 200, or 600 and watch the statistics change."))
    changed = [10, 15, 15, 20, 25, 30, outlier]
    ctx.show_descriptive_stats(changed, label_prefix="New ")
    observed = st.radio(
        ctx.content_get("level_copy.level_1_observe", "Did that match what you expected?"),
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l1_observe",
    )
    if observed:
        ctx.record_completion_once(pid, 1, "L1_OBSERVE", observed)
        st.caption(f"Observation recorded: {observed}")

    q = ctx.answer_radio(
        ctx.content_get("level_copy.level_1_q1", "Which statistic for the **typical commute time** changes the most because of the **very large outlier**?"),
        ["Mean", "Median", "Mode", "They all change equally"],
        key="l1q1",
    )
    if st.button("Lock answer", key="l1submit1"):
        if not prediction or not observed:
            ctx.show_challenge_status_box(
                "one-wrong",
                "Required steps missing",
                "Make a prediction and record whether the result matched before answering Question 1.",
            )
        else:
            ctx.score_answer(
                pid,
                1,
                "L1_OUTLIER",
                q,
                q == "Mean",
                25,
                correct_answer="Mean",
                explanation=ctx.content_get("level_copy.level_1_q1_explanation", "The mean uses every value, so one very large value pulls it up."),
            )

    st.markdown(ctx.content_get("level_copy.level_1_transition", "Let's see if the same idea holds somewhere else."))

    st.subheader("Question 2")
    ctx.show_challenge_acknowledgement(pid, "L1_CENTER")
    hospital_base_waits = [8, 10, 11, 12, 13, 14]
    st.write(ctx.content_get("level_copy.level_1_hospital_intro", "A hospital usually sees wait times close to 10 minutes."))
    st.write(hospital_base_waits)
    hospital_outlier = st.number_input(
        ctx.content_get("level_copy.level_1_hospital_outlier_input", "Add one **unusually long wait time**"),
        min_value=30,
        max_value=300,
        value=90,
        step=5,
        key="l1_hospital_outlier",
    )
    hospital_waits = hospital_base_waits + [hospital_outlier]

    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("**Before the outlier**")
        st.metric("Mean", f"{np.mean(hospital_base_waits):.1f}")
        st.metric("Median", f"{np.median(hospital_base_waits):.1f}")
    with after_col:
        st.markdown("**After the outlier**")
        st.metric("Mean", f"{np.mean(hospital_waits):.1f}")
        st.metric("Median", f"{np.median(hospital_waits):.1f}")

    st.write(ctx.content_get(
        "level_copy.level_1_hospital_prompt",
        "One patient waited much longer than usual. The hospital wants one number to describe a typical patient's wait.",
    ))
    q2 = ctx.answer_radio(
        ctx.content_get("level_copy.level_1_q2", "Which statistic would you report for the **typical wait**?"),
        ["Mean", "Median", "Mode", "Range"],
        key="l1q2",
    )
    if st.button("Lock answer", key="l1submit2"):
        ctx.score_answer(
            pid,
            1,
            "L1_CENTER",
            q2,
            q2 == "Median",
            25,
            correct_answer="Median",
            explanation=ctx.content_get("level_copy.level_1_q2_explanation", "The median stays close to the usual waits because one unusually long wait does not pull it much."),
        )
    reflection = st.radio(
        ctx.content_get(
            "level_copy.level_1_reflection",
            "Finish this thought: when data has an extreme outlier, I should check ______ before describing a typical value.",
        ),
        ["mean and median", "only the largest value", "only the sample size", "only the mode"],
        index=None,
        key="l1_reflection",
    )
    if reflection:
        ctx.record_completion_once(pid, 1, "L1_REFLECT", reflection)

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 1):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L1_BONUS")
        q3 = ctx.answer_radio(
            ctx.content_get("level_copy.level_1_bonus_q", "If one value becomes a **very large outlier** and the smallest value stays the same, what happens to the **range**?"),
            ["The range increases", "The range decreases", "The range stays the same", "The range becomes the median"],
            key="l1q3",
        )
        if st.button("Lock answer", key="l1submit3"):
            ctx.score_answer(
                pid,
                1,
                "L1_BONUS",
                q3,
                q3 == "The range increases",
                25,
                correct_answer="The range increases",
                explanation=ctx.content_get(
                    "level_copy.level_1_bonus_explanation",
                    "Range is maximum minus minimum. If the maximum gets larger and the minimum stays the same, the range increases.",
                ),
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_level_progress(pid, 1)
    ctx.show_next_button()
