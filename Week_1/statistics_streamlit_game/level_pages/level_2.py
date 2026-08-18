import numpy as np
import pandas as pd
import streamlit as st


def render(ctx):
    pid = ctx.pid
    st.header(ctx.STORY["levels"][2])
    ctx.show_youtube_resources("level_2")
    ctx.show_level_progress(pid, 2)
    st.info(ctx.content_get("level_copy.level_2_focus", "This challenge is about **spread**: how close together or far apart the values are."))
    ctx.show_level_2_formulas()
    st.write(ctx.content_get(
        "level_copy.level_2_intro",
        "Two machines make parts near 10 units. Look at the values first, then decide which machine is more consistent.",
    ))

    machine_a = np.array([9.9, 10.0, 10.0, 10.0, 10.1])
    machine_b = np.array([6, 8, 10, 12, 14])
    st.dataframe(pd.DataFrame({"Machine A": machine_a, "Machine B": machine_b}), hide_index=True, width="stretch")

    st.subheader("Question 1")
    ctx.show_challenge_acknowledgement(pid, "L2_CONSISTENCY")
    q = ctx.answer_radio(
        ctx.content_get("level_copy.level_2_q1", "Both machines have the same **mean**. Which machine is more **consistent**?"),
        ["Machine A", "Machine B", "They are equally consistent", "There is not enough information"],
        key="l2q1",
    )
    if st.button("Lock answer", key="l2submit1"):
        ctx.score_answer(
            pid,
            2,
            "L2_CONSISTENCY",
            q,
            q == "Machine A",
            30,
            correct_answer="Machine A",
            explanation=ctx.content_get("level_copy.level_2_q1_explanation", "Machine A's values stay closer to 10, so its standard deviation is smaller."),
        )
    if "L2_CONSISTENCY" in ctx.correct_challenges(pid):
        with st.expander("Show mean and standard deviation", expanded=True):
            df = pd.DataFrame({
                "Machine": ["A", "B"],
                "Mean": [machine_a.mean(), machine_b.mean()],
                "Sample SD": [machine_a.std(ddof=1), machine_b.std(ddof=1)],
            })
            st.dataframe(df, hide_index=True, width="stretch")
            st.info(ctx.content_get("level_copy.level_2_reveal", "Same center. Different variability."))

    st.subheader("Question 2")
    ctx.show_challenge_acknowledgement(pid, "L2_SD")
    sd_prediction = st.radio(
        ctx.content_get("level_copy.level_2_prediction", "Before you move the slider: what do you think increasing standard deviation from 5 to 20 will do?"),
        ["Make data narrower", "Make data wider", "Move the mean", "No effect"],
        index=None,
        key="l2_sd_prediction",
    )
    if sd_prediction:
        ctx.record_completion_once(pid, 2, "L2_PREDICT_SD", sd_prediction)
        st.caption(f"Prediction recorded: {sd_prediction}")

    spread = st.slider(ctx.content_get("level_copy.level_2_sd_input", "Choose a standard deviation for a process"), 1, 30, 10)
    st.caption(ctx.content_get("level_copy.level_2_sd_caption", "A larger standard deviation means values are farther from the mean."))
    np.random.seed(7)
    sample = np.random.normal(50, spread, 1200)
    hist = np.histogram(sample, bins=20)
    chart = pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1], 1))
    st.bar_chart(chart)
    st.caption(ctx.content_get("level_copy.level_2_chart_caption", "A larger standard deviation makes the chart wider."))

    q2 = ctx.answer_radio(
        ctx.content_get("level_copy.level_2_q2", "As **standard deviation** increases, what happens to the **data values** in the chart?"),
        ["They become more spread out", "They become narrower", "The mean must increase", "The sample size becomes zero"],
        key="l2q2",
    )
    if st.button("Lock answer", key="l2submit2"):
        if not sd_prediction:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Make a prediction before answering Question 2.")
        else:
            ctx.score_answer(
                pid,
                2,
                "L2_SD",
                q2,
                q2 == "They become more spread out",
                30,
                correct_answer="They become more spread out",
                explanation=ctx.content_get("level_copy.level_2_q2_explanation", "Standard deviation measures typical distance from the mean."),
            )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 2):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L2_BONUS")
        q3 = ctx.answer_radio(
            ctx.content_get("level_copy.level_2_bonus_q", "Which quantity is the square of the **standard deviation**?"),
            ["Variance", "Mean", "Median", "Range"],
            key="l2q3",
        )
        if st.button("Lock answer", key="l2submit3"):
            ctx.score_answer(
                pid,
                2,
                "L2_BONUS",
                q3,
                q3 == "Variance",
                30,
                correct_answer="Variance",
                explanation=ctx.content_get("level_copy.level_2_bonus_explanation", "Variance is standard deviation squared."),
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_next_button()
