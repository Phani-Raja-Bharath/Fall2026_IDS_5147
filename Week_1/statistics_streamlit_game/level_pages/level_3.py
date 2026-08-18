import streamlit as st


def render(ctx):
    pid = ctx.pid
    st.header("Level 3 - Distribution Junction")
    ctx.show_scaffold_note(3)
    ctx.show_youtube_resources("level_3")
    st.markdown(ctx.STORY["levels"][3])
    ctx.show_level_progress(pid, 3)
    st.write("Review all six distributions here. Then pick the distribution that matches each situation.")
    ctx.show_distribution_reference()

    questions = [
        ("L3_Q1", "**Sensor measurement noise** clustered around a target value", ["Normal", "Poisson", "Bernoulli", "Uniform"], "Normal"),
        ("L3_Q2", "One **success/failure** event with probability p", ["Uniform", "Bernoulli", "Exponential", "Normal"], "Bernoulli"),
        ("L3_Q3", "**Number of defective products** in a batch of 20 separate products", ["Binomial", "Normal", "Uniform", "Exponential"], "Binomial"),
        ("L3_Q4", "Every value between **0 and 100** is **equally likely**", ["Poisson", "Uniform", "Exponential", "Binomial"], "Uniform"),
    ]
    explanations = {
        "L3_Q1": "Normal values cluster around a center.",
        "L3_Q2": "Bernoulli is for one yes/no trial.",
        "L3_Q3": "Binomial counts successes across fixed yes/no trials.",
        "L3_Q4": "Uniform gives every value in the range the same chance.",
    }
    hints = {
        "L3_Q1": "Does the value cluster around a center, or is it spread evenly across a range?",
        "L3_Q2": "This describes exactly one trial with two possible outcomes.",
        "L3_Q3": "You're counting successes across a fixed number of separate yes/no trials.",
        "L3_Q4": "No value in the range is any more likely than another.",
    }

    for index, (cid, prompt, options, correct) in enumerate(questions, 1):
        st.subheader(f"Question {index} - Junction Track")
        st.markdown(f"**Question {index}:** {prompt}")
        ctx.show_challenge_acknowledgement(pid, cid)
        ctx.show_optional_hint(cid, hints[cid])
        answer = ctx.answer_radio(f"**Question {index}:** Choose the **matching distribution**.", options, key=cid)
        if st.button("Submit distribution choice", key=f"{cid}_submit"):
            ctx.score_answer(
                pid,
                3,
                cid,
                answer,
                answer == correct,
                20,
                correct_answer=correct,
                explanation=explanations[cid],
            )

    st.subheader("Bonus Question - Make-Up XP")
    if ctx.bonus_unlocked(pid, 3):
        st.caption("Optional. Use this to earn back missed XP.")
        st.markdown("**Bonus Question:** The time between machine breakdowns is continuous and memoryless.")
        ctx.show_challenge_acknowledgement(pid, "L3_BONUS")
        ctx.show_optional_hint("L3_BONUS", "This is about the waiting time until the next event, not a count.")
        answer = ctx.answer_radio(
            "**Bonus Question:** Choose the **matching distribution**.",
            ["Exponential", "Binomial", "Uniform", "Normal"],
            key="L3_BONUS",
        )
        if st.button("Submit bonus choice", key="L3_BONUS_submit"):
            ctx.score_answer(
                pid,
                3,
                "L3_BONUS",
                answer,
                answer == "Exponential",
                20,
                correct_answer="Exponential",
                explanation="Exponential is often used for time between events.",
            )
    else:
        st.caption("Unlocks if you miss a track above.")
    ctx.show_next_button()
